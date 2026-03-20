#!/usr/bin/env python3
"""
Voice Transcription using OpenRouter API with Google Gemini.

Two modes:
  - fast (default): Gemini 3 Flash — optimized for speed, parallel chunked transcription
  - pro:            Gemini 3.1 Pro  — optimized for accuracy, parallel chunked transcription

Usage:
    python3 transcribe.py --input audio.mp3                        # fast mode (default)
    python3 transcribe.py --input audio.mp3 --mode pro             # pro mode (accuracy)
    python3 transcribe.py --input audio.m4a -o transcript.txt -l zh --mode fast

Environment:
    OPENROUTER_API_KEY  - Required. Must be set as an environment variable.
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


# ── Constants ─────────────────────────────────────────────────────────────────

API_URL      = "https://openrouter.ai/api/v1/chat/completions"
CHUNK_MB_MAX = 18          # stay safely under 20 MB API limit
PRINT_LOCK   = threading.Lock()

MODES = {
    "fast": {"model": "google/gemini-3-flash-preview", "label": "⚡ Fast Mode (Gemini 3 Flash)"},
    "pro":  {"model": "google/gemini-3.1-pro-preview", "label": "🎯 Pro Mode (Gemini 3.1 Pro)"},
}

SUPPORTED_FORMATS = {
    ".mp3": "mp3", ".wav": "wav", ".m4a": "m4a", ".ogg": "ogg",
    ".flac": "flac", ".aac": "aac", ".aiff": "aiff", ".wma": "wma",
    ".webm": "webm", ".opus": "opus",
}

LANGUAGE_PROMPTS = {
    "auto": "Transcribe this audio accurately. Auto-detect the language and output ONLY the transcription text, nothing else.",
    "zh":   "請將這段音訊精確地轉錄為繁體中文文字。只輸出轉錄的文字內容，不要加入任何額外說明。",
    "en":   "Transcribe this audio accurately into English. Output ONLY the transcription text, nothing else.",
    "ja":   "この音声を正確に日本語テキストに書き起こしてください。書き起こしテキストのみを出力してください。",
    "ko":   "이 오디오를 한국어 텍스트로 정확하게 전사해 주세요. 전사 텍스트만 출력해 주세요.",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def log(msg: str):
    with PRINT_LOCK:
        print(msg, file=sys.stderr, flush=True)


def get_api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        log("ERROR: OPENROUTER_API_KEY not set.")
        log("  Set it: export OPENROUTER_API_KEY='sk-or-...'")
        sys.exit(1)
    return key


def ffmpeg_available() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def get_duration_seconds(path: Path) -> float:
    """Get audio duration via ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def compress_to_mp3(src: Path, dest: Path, bitrate: str = "48k"):
    """Re-encode audio to mono MP3 at low bitrate (good enough for speech)."""
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src),
         "-ac", "1", "-ar", "16000", "-b:a", bitrate, str(dest)],
        capture_output=True, check=True,
    )


def split_audio(src: Path, dest_dir: Path, chunk_sec: int) -> list[Path]:
    """Split audio into fixed-duration MP3 chunks. Returns sorted list of paths."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    pattern = dest_dir / "chunk_%04d.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src),
         "-f", "segment", "-segment_time", str(chunk_sec),
         "-ac", "1", "-ar", "16000", "-b:a", "48k", str(pattern)],
        capture_output=True, check=True,
    )
    return sorted(dest_dir.glob("chunk_*.mp3"))


def api_transcribe(audio_b64: str, fmt: str, prompt: str,
                   model: str, api_key: str) -> str:
    """Send one audio chunk to OpenRouter and return the transcription text."""
    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "input_audio", "input_audio": {"data": audio_b64, "format": fmt}},
            ],
        }],
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://claude-skill-voice-transcription",
            "X-Title": "Claude Voice Transcription Skill",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        try:
            msg = json.loads(body).get("error", {}).get("message", body)
        except json.JSONDecodeError:
            msg = body[:300]
        raise RuntimeError(f"HTTP {e.code}: {msg}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error: {e.reason}") from e

    try:
        return result["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected response: {json.dumps(result)[:300]}") from e


def transcribe_chunk(idx: int, total: int, chunk_path: Path,
                     prompt: str, model: str, api_key: str) -> tuple[int, str]:
    """Transcribe a single chunk. Returns (index, text)."""
    audio_b64 = base64.b64encode(chunk_path.read_bytes()).decode()
    size_mb = chunk_path.stat().st_size / 1024 / 1024
    log(f"  [{idx+1}/{total}] Sending {chunk_path.name} ({size_mb:.1f} MB)...")
    text = api_transcribe(audio_b64, "mp3", prompt, model, api_key)
    log(f"  [{idx+1}/{total}] Done ✓")
    return idx, text


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Transcribe audio using OpenRouter API + Gemini (parallel)"
    )
    parser.add_argument("--input",   "-i", required=True, help="Audio file to transcribe")
    parser.add_argument("--output",  "-o", default=None,  help="Output text file (default: stdout)")
    parser.add_argument("--language","-l", default="auto",help="Language: auto, zh, en, ja, ko… (default: auto)")
    parser.add_argument("--prompt",  "-p", default=None,  help="Custom prompt (overrides language default)")
    parser.add_argument("--mode",         default="fast", choices=["fast", "pro"],
                        help="Transcription mode: fast (Gemini 3 Flash) or pro (Gemini 3.1 Pro). Default: fast")
    parser.add_argument("--model",   "-m", default=None,  help="Override model ID (ignores --mode)")
    parser.add_argument("--workers", "-w", default=10, type=int, help="Parallel workers for chunked files (default: 10)")
    args = parser.parse_args()

    audio_path = Path(args.input)
    if not audio_path.exists():
        log(f"ERROR: File not found: {audio_path}")
        sys.exit(1)

    suffix = audio_path.suffix.lower()
    if suffix not in SUPPORTED_FORMATS:
        log(f"ERROR: Unsupported format '{suffix}'. Supported: {', '.join(SUPPORTED_FORMATS)}")
        sys.exit(1)

    # Resolve model from --mode (or --model override)
    if args.model:
        model = args.model
        mode_label = f"Custom ({model})"
    else:
        mode_info = MODES[args.mode]
        model = mode_info["model"]
        mode_label = mode_info["label"]

    api_key = get_api_key()
    prompt  = args.prompt or LANGUAGE_PROMPTS.get(args.language, LANGUAGE_PROMPTS["auto"])
    size_mb = audio_path.stat().st_size / 1024 / 1024

    log(f"Input : {audio_path.name}  ({size_mb:.1f} MB)")
    log(f"Mode  : {mode_label}")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # ── Small file: send directly (no chunking needed) ──────────────────
        if size_mb <= CHUNK_MB_MAX and suffix == ".mp3":
            log("Single request (file is small enough)...")
            audio_b64 = base64.b64encode(audio_path.read_bytes()).decode()
            try:
                text = api_transcribe(audio_b64, "mp3", prompt, model, api_key)
            except RuntimeError as e:
                log(f"ERROR: {e}")
                sys.exit(1)
            parts = [text]

        else:
            if not ffmpeg_available():
                log("ERROR: ffmpeg not found. Install ffmpeg to process large/non-MP3 files.")
                sys.exit(1)

            # ── Compress if needed ───────────────────────────────────────────
            if size_mb > CHUNK_MB_MAX or suffix != ".mp3":
                log(f"Compressing to MP3 (48kbps mono)...")
                compressed = tmp / "compressed.mp3"
                compress_to_mp3(audio_path, compressed)
                size_after = compressed.stat().st_size / 1024 / 1024
                log(f"  {size_mb:.1f} MB → {size_after:.1f} MB")
                work_file = compressed
            else:
                work_file = audio_path

            # ── Split into chunks ────────────────────────────────────────────
            duration = get_duration_seconds(work_file)
            # Auto-size chunks so each worker gets exactly one chunk
            chunk_sec = max(30, int(duration / args.workers) + 1)
            n_chunks = args.workers
            log(f"Splitting into {n_chunks} chunks (~{chunk_sec}s each, 1 per worker)...")
            chunks = split_audio(work_file, tmp / "chunks", chunk_sec)
            log(f"  → {len(chunks)} chunks | {args.workers} parallel workers")

            # ── Parallel transcription ───────────────────────────────────────
            results: dict[int, str] = {}
            errors: list[str] = []

            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                futures = {
                    pool.submit(transcribe_chunk, i, len(chunks), c, prompt, model, api_key): i
                    for i, c in enumerate(chunks)
                }
                for future in as_completed(futures):
                    try:
                        idx, text = future.result()
                        results[idx] = text
                    except RuntimeError as e:
                        chunk_idx = futures[future]
                        errors.append(f"Chunk {chunk_idx}: {e}")
                        log(f"  ERROR chunk {chunk_idx}: {e}")

            if errors:
                log(f"\nWARNING: {len(errors)} chunk(s) failed:")
                for err in errors:
                    log(f"  {err}")

            # Reassemble in order
            parts = [results[i] for i in sorted(results)]

    # ── Output ────────────────────────────────────────────────────────────────
    full_text = "\n\n".join(parts)

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(full_text, encoding="utf-8")
        log(f"Saved → {out}")
    else:
        print(full_text)

    log("Done.")


if __name__ == "__main__":
    main()
