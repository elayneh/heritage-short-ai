# ትግል ለ30 (The Struggle for 30)

Automated AI short-film pipeline for the 10 Academy challenge. A taxi ride from Bulbula to Bole in Addis Ababa, told from the front cabin.

Status: Phase 1. The storyboard, Gemini TTS narration, and FFmpeg radio cut are implemented. This pipeline does not call image, video, or music models.

## Quick start

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
# add GEMINI_API_KEY to .env
make validate
make test
```

## Commands

| Command | What it does |
|---|---|
| `make validate` | Validate `storyboard.json` before any model call |
| `make test` | Run unit tests with mocked API responses |
| `make narration` | Generate all 11 narration clips with Gemini TTS |
| `make narration-shot SHOT=S05` | Regenerate one shot |
| `make radio-cut` | Build the black-screen radio cut with subtitles and placeholder music |
| `make setup` | Install dependencies into `.venv` |

Narration is a paid API call. Run `make narration` only when approved.

Dry run, no API key needed:

```sh
.venv/bin/python -m pipeline.narration --all --dry-run
```

## Pipeline

1. `storyboard.json` is the source of truth for every shot, prompt, reference, narration line, subtitle, music cue, sound effect, camera note, and seed.
2. `schema/storyboard.schema.json` plus semantic checks reject bad storyboards before any API call.
3. Gemini TTS writes one WAV per shot to `outputs/narration/`. Successful clips are cached by input hash.
4. FFmpeg builds `outputs/radio_cut/radio_cut.mp4` with a black background, Amharic narration, burned-in English subtitles, placeholder music, and an AI disclosure end card.

The radio cut exists to test story, narration, pacing, and audience response before spending money on visuals.

## Layout

```text
pipeline/          shared modules, narration client, radio cut builder
schema/            storyboard JSON Schema
tests/             unit tests, no network calls
storyboard.json    the 11-shot film
runs.jsonl         append-only model call log
outputs/           generated narration and radio cut (gitignored)
references/        character and vehicle reference notes
```

## Configuration

Copy `.env.example` to `.env` and set `GEMINI_API_KEY`. The TTS model, voice, style, API mode, timeout, and retry settings are environment variables. See `.env.example`.

The default is the Gemini Interactions API with `gemini-3.8-flash-tts`. Set `GEMINI_TTS_API=generateContent` to use `gemini-2.5-flash-preview-tts` through `generateContent`. Verify model IDs in the official Gemini documentation before changing them.

## Documentation

- `DESIGN.md`: creative intent and visual direction
- `ARCHITECTURE.md`: modules, data flow, caching, logging
- `EXPERIMENTS.md`: what has and has not been tested
- `FAILURES.md`: known limitations and open risks
- `COSTS.md`: spend so far and how costs are recorded
- `ETHICS.md`: consent, disclosure, and representation rules
- `AGENTS.md`: commands and repo gotchas for coding agents
