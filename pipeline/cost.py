RATES = {
    "gemini-2.5-flash-preview-tts": {
        "input_per_million": 0.50,
        "output_per_million": 10.00,
    },
}


def extract_usage(data):
    usage = data.get("usage") or data.get("usageMetadata") or {}
    input_tokens = (
        usage.get("promptTokenCount")
        or usage.get("input_tokens")
        or usage.get("inputTokenCount")
    )
    output_tokens = (
        usage.get("candidatesTokenCount")
        or usage.get("output_tokens")
        or usage.get("outputTokenCount")
    )
    if input_tokens is None and output_tokens is None:
        return None
    return {
        "input_tokens": input_tokens or 0,
        "output_tokens": output_tokens or 0,
    }


def estimate_cost(model, usage):
    if usage is None:
        return None, "usage_not_returned"

    rates = RATES.get(model)
    if rates is None:
        return None, "rate_not_configured"

    cost = (
        usage["input_tokens"] / 1_000_000 * rates["input_per_million"]
        + usage["output_tokens"] / 1_000_000 * rates["output_per_million"]
    )
    return round(cost, 6), "estimated"
