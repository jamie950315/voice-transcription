---
name: voice-transcription
description: "**Voice Transcription**: Transcribe audio files to text using OpenRouter API with Google Gemini. Two modes: Fast (Gemini 3 Flash, speed-optimized) and Pro (Gemini 3.1 Pro, accuracy-optimized). Supports multiple languages and audio formats (mp3, wav, m4a, ogg, flac, aac, etc.). Use when the user uploads an audio file and wants it transcribed, or mentions voice transcription, speech-to-text, or audio-to-text."
---

# Voice Transcription Skill

## Overview

This skill transcribes audio files into text using the **OpenRouter API**. Large files are automatically compressed, split, and transcribed in parallel for speed. It supports multiple languages and various audio formats.

### Two Modes

| Mode | Model | Best for |
|------|-------|----------|
| `fast` (default) | `google/gemini-3-flash-preview` | Speed — quick turnaround, good enough for most use cases |
| `pro` | `google/gemini-3.1-pro-preview` | Accuracy — best quality, slower and costs more |

If the user doesn't specify, use **fast** mode. Use **pro** mode when the user explicitly asks for higher accuracy or mentions "pro mode".

## Prerequisites

- An **OpenRouter API Key** is required
- Set the environment variable `OPENROUTER_API_KEY` before running
- If the env var is not set, ask the user to provide their key

## How to Use

When the user uploads an audio file and wants it transcribed:

1. **Locate the audio file** — check the uploads directory or the path the user provides
2. **Run the transcription script immediately** — do NOT check the API key beforehand; the script handles its own validation:

```bash
# Fast mode (default)
python3 ~/.claude/skills/voice-transcription/scripts/transcribe.py \
  --input "/path/to/audio/file.mp3" \
  --output "/path/to/output/transcription.txt" \
  --language "auto"

# Pro mode (higher accuracy)
python3 ~/.claude/skills/voice-transcription/scripts/transcribe.py \
  --input "/path/to/audio/file.mp3" \
  --output "/path/to/output/transcription.txt" \
  --language "auto" \
  --mode pro
```

### Script Arguments

| Argument     | Required | Description                                                         |
|-------------|----------|---------------------------------------------------------------------|
| `--input`   | Yes      | Path to the audio file                                              |
| `--output`  | No       | Path to save transcription text (default: prints to stdout)         |
| `--language`| No       | Target language hint: `auto`, `zh`, `en`, `ja`, `ko`, etc. (default: `auto`) |
| `--prompt`  | No       | Custom prompt for the transcription (overrides default)             |
| `--mode`    | No       | `fast` (Gemini 3 Flash) or `pro` (Gemini 3.1 Pro). Default: `fast` |
| `--model`   | No       | Override model ID directly (ignores --mode)                         |
| `--workers` | No       | Parallel workers for chunked files (default: 10)                    |

### Supported Audio Formats

`mp3`, `wav`, `m4a`, `ogg`, `flac`, `aac`, `aiff`, `wma`, `webm`

### Supported Languages

The model supports multilingual transcription. Use `--language auto` (default) for automatic detection, or provide an ISO 639-1 code to hint the language.

## Workflow Example

```
User: "幫我把這個音訊檔轉成文字"
Claude:
  1. Read this SKILL.md
  2. Find the uploaded audio file
  3. Run: python3 scripts/transcribe.py --input /path/to/audio.mp3
  4. Read the transcription output
  5. Present the transcription to the user

User: "用 pro mode 幫我轉錄，要最精確的"
Claude:
  1. Read this SKILL.md
  2. Find the uploaded audio file
  3. Run: python3 scripts/transcribe.py --input /path/to/audio.mp3 --mode pro
  4-5. (same as above)
```

## Error Handling

- If the API key is missing → ask the user to set `OPENROUTER_API_KEY`
- If the audio file is too large → the script auto-compresses and splits it (requires ffmpeg)
- If the API returns an error → show the error message and suggest retrying
- If transcription is empty → suggest the audio may be silent or corrupted

## Notes

- The script reads the API key from the `OPENROUTER_API_KEY` environment variable
- Audio files are base64-encoded before sending to the API
- Large files are auto-compressed, split by worker count, and transcribed in parallel
- Transcription quality depends on audio clarity and the model's capabilities
