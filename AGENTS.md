# AGENTS.md

## Scope

Phase 1 only: storyboard, Amharic narration, and the radio cut. Do not generate images, video, or music through paid APIs. Ask before any paid API call.

## Environment

- Python 3.12 venv at `.venv`. Use `make` targets or `.venv/bin/python`.
- Install dependencies with `make setup`.
- Secrets live in `.env`. Never commit it, print it, or paste it into logs.
- `GEMINI_TTS_API=interactions` uses `gemini-3.8-flash-tts` by default. `generateContent` uses `gemini-2.5-flash-preview-tts`. Verify model IDs in Google docs before changing defaults.

## Commands

- `make validate` validates `storyboard.json`.
- `make test` runs pytest on `tests/` only.
- `make narration` generates all narration. This is a paid Gemini call.
- `make narration-shot SHOT=S01` regenerates one shot.
- `make radio-cut` builds `outputs/radio_cut/radio_cut.mp4` from existing narration.
- `.venv/bin/python -m pipeline.narration --all --dry-run` shows hashes and cache state without an API call.

## Gotchas

- `pytest.ini` restricts collection to `tests/`. Root `test_cloudflare.py` is a manual paid smoke script. Do not run it in tests.
- Homebrew ffmpeg 9.1 here has no `drawtext` or `subtitles` filters. The radio cut renders text with Pillow using Arial and KefaIII, then overlays PNGs. Do not add those filters.
- The radio cut needs `outputs/narration/S01.wav` through `S11.wav`. Missing files fail with a hint to run `make narration`.
- Narration longer than its shot is warned and extended by default. `--strict` fails instead.
- `--narration-dir` and `--out` let you smoke test with synthetic WAVs without touching real outputs.
- Cache is content addressed at `.cache/narration/<hash>.wav`. The hash covers narration text, model, voice, style, and API. Change one and only that shot misses. `--force` bypasses the cache.
- `runs.jsonl` is append-only JSONL for model calls. Never log credentials.
- Generated media and `.cache/` are gitignored. Do not commit outputs or `.env`.

## Source of truth

- `storyboard.json` drives the pipeline. Edit it, then run `make validate`.
- Schema: `schema/storyboard.schema.json`. Semantic checks: `pipeline/storyboard.py`.
- Creative intent: `DESIGN.md`. Architecture: `ARCHITECTURE.md`. Costs and failures: `COSTS.md`, `FAILURES.md`.

## Style

No em dashes. No emojis. No comments unless the language requires them.
