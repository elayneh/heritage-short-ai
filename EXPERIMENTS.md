# Experiments

## Status

No model experiments and no audience tests have been run in Phase 1.

No paid Gemini, Wan, or ACE-Step calls were made during this Phase 1 implementation. No narration audio exists yet. The earlier manual Cloudflare test image at `outputs/images/test.jpg` is outside the pipeline and is not counted here.

A local FFmpeg smoke run with synthetic tone WAVs confirmed that the radio cut assembles a valid 1080x1920, 30 fps, 88 second MP4 with subtitles, end card, and mixed audio. That run is not a creative result and its audio is not narration.

## Planned experiments

| ID | Question | Method | Success signal | Status |
|---|---|---|---|---|
| E1 | Does the default Gemini voice fit the narrator? | Generate all 11 lines, listen for tone, pace, and Amharic clarity | Natural, consistent, no mispronunciation that changes meaning | Not run |
| E2 | Does each narration fit its shot? | Compare measured WAV duration to `duration_seconds` | All shots within allocation, or only intentional overflow | Not run |
| E3 | Does the radio cut hold attention? | Show to 5 to 10 target viewers | Viewers describe the driver's struggle as the main theme | Not run |
| E4 | Are subtitles readable at 9:16? | Review on a phone at arm's length | No missed lines, no clipping | Not run |
| E5 | Is the ending clear? | Ask viewers to restate the closing line | Most restate the passenger versus driver contrast | Not run |

## Recording results

When an experiment is run, add a row with the date, configuration hash, and raw observations. Do not write results from memory. Do not estimate audience feedback.

Template:

```text
Experiment:
Date:
Model and settings:
Input hash:
Command:
Observed:
Decision:
```

## Audience feedback

None collected. The sections in `DESIGN.md` remain pending until real viewers respond.
