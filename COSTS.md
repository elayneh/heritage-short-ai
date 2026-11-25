# Costs

## Spend to date

The Phase 1 implementation made no paid model calls. Recorded pipeline spend: 0 USD.

The only API image on disk, `outputs/images/test.jpg`, came from an earlier manual Cloudflare test. That test may have incurred a small charge, but no amount is recorded in this repo and it is outside the pipeline.

## How costs are recorded

Every model call appends a record to `runs.jsonl` with:

- `cost_usd`: a number, or null when it cannot be computed
- `cost_basis`: `estimated`, `usage_not_returned`, `rate_not_configured`, `request_failed`, or `local_compute`
- `usage`: token counts when the provider returns them

No total is invented. If the provider does not return usage, the cost stays null and the basis explains why.

## Configured rates

Only one TTS model has a rate table in `pipeline/cost.py`:

| Model | Input | Output |
|---|---|---|
| `gemini-2.5-flash-preview-tts` | 0.50 USD per 1M text tokens | 10.00 USD per 1M audio tokens |

Source: Google Gemini API pricing for Gemini 2.5 Flash TTS, checked November 2026.

`gemini-3.8-flash-tts` has no configured rate, so its cost is logged as `rate_not_configured` even when usage is returned. Add a verified rate before relying on its cost figures.

## Cost areas not yet used

| Stage | Provider | Status |
|---|---|---|
| Images | Cloudflare Workers AI FLUX | Not used in Phase 1 |
| Video | Wan 2.2 on Kaggle GPU | Not used |
| Music | ACE-Step | Not used, placeholder drone only |
| Narration | Gemini TTS | Implemented, not called |

No estimates are given for these stages because no verified per-shot usage or pricing has been measured in this repo.

## Before any paid run

1. Run `make validate`.
2. Run `.venv/bin/python -m pipeline.narration --all --dry-run` and confirm the cache misses.
3. Get approval for the spend.
4. Run the smallest useful batch first, usually one shot with `make narration-shot`.
5. Check `runs.jsonl` for latency, usage, and cost basis before running the rest.
