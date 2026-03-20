# Voice Transcription

Transcribe audio files to text using the [OpenRouter API](https://openrouter.ai/) with Google Gemini models. Large files are automatically compressed, split, and transcribed in parallel.

## Features

- **Two modes**: Fast (Gemini 3 Flash) and Pro (Gemini 3.1 Pro)
- **Parallel chunked transcription** for large files
- **Auto-compression** via ffmpeg (48kbps mono MP3)
- **Multi-language** support with auto-detection
- **No dependencies** beyond Python 3 standard library (+ ffmpeg for large/non-MP3 files)

## Modes

| Mode | Model | Best for |
|------|-------|----------|
| `fast` (default) | `google/gemini-3-flash-preview` | Speed — quick turnaround |
| `pro` | `google/gemini-3.1-pro-preview` | Accuracy — best quality |

## Supported Formats

`mp3` `wav` `m4a` `ogg` `flac` `aac` `aiff` `wma` `webm` `opus`

## Prerequisites

- Python 3.10+
- [ffmpeg](https://ffmpeg.org/) (only required for large or non-MP3 files)
- An [OpenRouter API key](https://openrouter.ai/keys)

## Usage

```bash
export OPENROUTER_API_KEY='sk-or-...'

# Fast mode (default)
python3 scripts/transcribe.py --input audio.mp3

# Pro mode
python3 scripts/transcribe.py --input audio.mp3 --mode pro

# Specify language and output file
python3 scripts/transcribe.py --input audio.m4a -o transcript.txt -l zh
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--input`, `-i` | Yes | Path to audio file |
| `--output`, `-o` | No | Output text file (default: stdout) |
| `--language`, `-l` | No | Language hint: `auto`, `zh`, `en`, `ja`, `ko` (default: `auto`) |
| `--mode` | No | `fast` or `pro` (default: `fast`) |
| `--prompt`, `-p` | No | Custom transcription prompt |
| `--model`, `-m` | No | Override model ID directly |
| `--workers`, `-w` | No | Parallel workers for chunked files (default: 10) |

## How It Works

1. **Small MP3 files** (< 18 MB) are sent directly to the API
2. **Large or non-MP3 files** are compressed to 48kbps mono MP3, split into chunks, and transcribed in parallel
3. Chunks are reassembled in order to produce the final transcript

## Claude Code Skill

This project is also a [Claude Code](https://claude.com/claude-code) skill. Drop it into `~/.claude/skills/` and Claude will automatically use it when you ask to transcribe audio files.

## License

MIT
