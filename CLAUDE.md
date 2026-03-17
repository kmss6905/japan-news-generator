# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This tool converts YouTube Japanese news videos into structured bilingual PDF learning materials. It extracts video content, uses Claude to generate Japanese/Korean bilingual tables, and renders a PDF with QR codes linking back to the source video.

## Common Commands

### Single Video Processing

```bash
# Via Claude Code skill (no API key needed — uses Claude session)
/japannews https://www.youtube.com/watch?v=VIDEO_ID

# Via Python directly (requires ANTHROPIC_API_KEY in .env)
python3 main.py <youtube_url> <output_path>
```

### Batch Processing (Google Sheets integration)

```bash
# Session mode — Part 1: fetch YouTube metadata (no Claude API cost)
python3 tools/batch_processor.py --fetch

# Session mode — Part 2: finalize after Claude generates markdown
python3 tools/batch_processor.py --finalize <row_number> <output_md_file>

# API mode — end-to-end via Anthropic API
python3 tools/batch_processor.py

# Dry run — list pending rows without processing
python3 tools/batch_processor.py --dry-run
```

### Environment Setup

```bash
cp .env.example .env
# Set ANTHROPIC_API_KEY and Google integration vars
export DYLD_LIBRARY_PATH=/opt/homebrew/lib  # Required on macOS for WeasyPrint
```

## Architecture

The pipeline runs in three sequential stages:

1. **`tools/fetch_youtube.py`** — Extracts video metadata (title, channel, upload_date, description) via `yt-dlp` and captions via `youtube-transcript-api`.

2. **`tools/text_to_markdown.py`** — Sends the extracted content to Claude (`claude-haiku-4-5-20251001`, max 4096 tokens) to produce structured markdown: H1 title, H2 timestamp sections, bilingual Japanese/Korean tables, and vocabulary lists.

3. **`tools/markdown_to_pdf.py`** — Converts markdown → HTML (via Pandoc), injects a base64 QR code into the H1 heading, then renders to PDF via WeasyPrint with Noto Sans JP fonts. H2 elements trigger page breaks.

**Batch pipeline adds:**
- **`tools/google_sheets.py`** — Reads pending YouTube URLs from a Google Sheet (service account auth), updates status per row (대기/실행중/완료/오류).
- **`tools/drive_uploader.py`** — Uploads generated PDF to Google Drive using OAuth2 user auth (token cached in `config/oauth_token.pickle`), returns a shareable link written back to the sheet.

## Key Implementation Details

- **macOS**: `DYLD_LIBRARY_PATH=/opt/homebrew/lib` must be set before running WeasyPrint. The `.claude/settings.local.json` passes this via `env` for skill/hook execution.
- **Session mode** (`--fetch` / `--finalize`) splits batch processing so Claude generates the markdown interactively without consuming Anthropic API quota — intermediate data passes through `/tmp/japannews_batch_{row}.json`.
- **Google Drive** uses OAuth2 (not service account) — first run opens a browser for consent; token auto-refreshes for up to 6 months (`config/oauth_token.pickle`).
- **Google Sheets** uses a service account (`config/credentials.json`) — share the target spreadsheet with the service account email.
- All sensitive files (`config/`, `output/`, `.env`) are gitignored.

## Output Format

- PDF saved to `output/{video_id}_{YYYYMMDD}.pdf`
- QR code linking to the YouTube URL appears next to the H1 title
- Each H2 section begins on a new page
- Tables contain Japanese sentences with Korean translations
