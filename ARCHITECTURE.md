# Architecture

## Data flow

```text
storyboard.json
  -> schema and semantic validation
  -> narration inputs (per shot)
  -> Gemini TTS client
  -> .cache/narration/<input-hash>.wav
  -> outputs/narration/S01.wav ... S11.wav
  -> FFmpeg radio cut
  -> outputs/radio_cut/radio_cut.mp4
```

`storyboard.json` is the only creative input. Each shot owns its prompts, references, narration, subtitle, music cue, sound effect cues, camera notes, and seed. Character and vehicle reference IDs are declared once at the top level and checked against every shot.

## Modules

| Module | Responsibility |
|---|---|
| `pipeline/config.py` | Repo paths, `.env` loading, Gemini TTS and retry configuration |
| `pipeline/hashing.py` | Canonical JSON and SHA-256 input hashes |
| `pipeline/cache.py` | Content-addressed file cache with atomic writes |
| `pipeline/retry.py` | Exponential backoff with jitter-free delay cap and retry predicate |
| `pipeline/logging_utils.py` | Append-only JSONL run log |
| `pipeline/cost.py` | Usage extraction and cost estimates for configured models |
| `pipeline/storyboard.py` | JSON Schema validation, duplicate IDs, duration and reference checks |
| `pipeline/narration.py` | Gemini TTS payloads, response parsing, caching, per-shot regeneration |
| `pipeline/radio_cut.py` | Timeline, subtitle and end card rendering, audio mix, MP4 assembly |
| `pipeline/validate.py` | CLI for storyboard validation |

## Validation order

`load_storyboard` reads the JSON, applies the schema, then runs semantic checks:

- 8 to 12 shots
- unique shot IDs
- total duration between 60 and 90 seconds
- declared total equals the sum of shot durations
- every character and vehicle reference exists

Any failure raises `StoryboardError` before credentials are loaded or an API call is made.

## Caching

The narration cache key is a SHA-256 hash of canonical JSON containing:

- narration text
- model ID
- voice
- style
- API mode

A cache hit copies the cached WAV to `outputs/narration/<shot>.wav`. A miss calls the model, writes the cache atomically, then writes the output copy. Editing one shot's narration does not invalidate other shots. `--force` ignores the cache for the selected shots.

## Logging

Every model call appends one JSON object to `runs.jsonl` with:

- timestamp, stage, shot ID
- provider, model, parameters
- seed when supported, plus `seed_supported`
- input hash, latency in milliseconds
- cost and cost basis
- usage when the provider returns it
- success, error, and retry events

Credentials are never placed in run records.

## Narration client

Two API modes are supported:

- `interactions`: `POST /v1beta/interactions` with `speech_metadata` style and `speech_config` voice. Default model is `gemini-3.8-flash-tts`. Unary responses are WAV.
- `generateContent`: `POST /v1beta/models/<model>:generateContent` with `responseModalities: ["AUDIO"]` and a prebuilt voice. Default model is `gemini-2.5-flash-preview-tts`. Raw PCM is wrapped into a 24 kHz mono WAV container.

Retries apply to HTTP 429, HTTP 5xx, network errors, and missing audio. Other 4xx errors fail immediately.

## Radio cut

The local FFmpeg build has no `drawtext` or `subtitles` filter, so text is rendered with Pillow:

- English subtitles use Arial and are drawn onto transparent 1080x1920 PNGs.
- The end card uses KefaIII for Amharic and Arial for English.
- FFmpeg overlays each PNG at its shot interval on a black 1080x1920, 30 fps canvas.

Audio is built in three steps:

1. Each narration WAV is resampled to 24 kHz mono and padded to its shot duration with `apad=whole_dur`. If narration is longer, it is not cut.
2. Padded segments are concatenated into one narration track.
3. A synthetic placeholder drone is mixed under the narration at low volume.

The final MP4 is H.264 with AAC audio, `yuv420p`, and fast start. The narration timing report is written next to the output.

## Extension points for later phases

- Add image generation behind the same cache and run logging pattern.
- Add video generation keyed by image hash, motion prompt, and seed.
- Add ACE-Step music keyed by music cue and duration.
- Replace placeholder music with generated stems and a real mix.
- Add per-shot visual consistency checks against character and vehicle references.
