import argparse
import base64
import io
import json
import shutil
import sys
import time
import wave
from pathlib import Path

import requests

from .cache import FileCache
from .config import (
    CACHE_DIR,
    NARRATION_DIR,
    RUNS_PATH,
    MissingCredentialError,
    load_gemini_tts_config,
    load_retry_config,
)
from .cost import estimate_cost, extract_usage
from .hashing import input_hash
from .logging_utils import RunLogger
from .retry import retry_call
from .storyboard import StoryboardError, load_storyboard, shot_by_id


class NarrationError(RuntimeError):
    pass


class NarrationAPIError(NarrationError):
    def __init__(self, status_code, message):
        self.status_code = status_code
        self.message = message
        super().__init__(f"HTTP {status_code}: {message}")


def narration_inputs(shot, config):
    return {
        "text": shot["narration_am"],
        "model": config.model,
        "voice": config.voice,
        "style": config.style,
        "api": config.api,
        "base_url": config.base_url,
    }


def build_interactions_payload(text, model, voice, style):
    return {
        "model": model,
        "input": [
            {
                "type": "user_input",
                "content": [
                    {
                        "type": "text",
                        "text": text,
                        "annotations": [
                            {"type": "speech_metadata", "style": style}
                        ],
                    }
                ],
            }
        ],
        "response_format": {"type": "audio"},
        "generation_config": {"speech_config": [{"voice": voice}]},
    }


def build_generate_content_payload(text, voice, style):
    spoken_text = f"{style} style: {text}" if style else text
    return {
        "contents": [{"parts": [{"text": spoken_text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": voice}
                }
            },
        },
    }


def extract_audio(data, api):
    if api == "interactions":
        for step in reversed(data.get("steps", [])):
            if step.get("type") != "model_output":
                continue
            for item in step.get("content", []):
                if item.get("type") == "audio" and item.get("data"):
                    return base64.b64decode(item["data"])
        output_audio = data.get("output_audio") or {}
        if output_audio.get("data"):
            return base64.b64decode(output_audio["data"])
        raise NarrationError("no audio data in interactions response")

    for candidate in data.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data") or {}
            if inline.get("data"):
                return base64.b64decode(inline["data"])
    raise NarrationError("no audio data in generateContent response")


def ensure_wav(audio_bytes):
    if audio_bytes[:4] == b"RIFF":
        return audio_bytes
    if len(audio_bytes) % 2 != 0:
        raise NarrationError("raw PCM audio has an odd byte length")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(24000)
        handle.writeframes(audio_bytes)
    return buffer.getvalue()


def synthesize_narration(text, config):
    headers = {
        "x-goog-api-key": config.api_key,
        "Content-Type": "application/json",
    }

    if config.api == "interactions":
        url = f"{config.base_url}/interactions"
        payload = build_interactions_payload(
            text, config.model, config.voice, config.style
        )
    elif config.api == "generateContent":
        url = (
            f"{config.base_url}/models/{config.model}:generateContent"
        )
        payload = build_generate_content_payload(
            text, config.voice, config.style
        )
    else:
        raise NarrationError(f"unsupported GEMINI_TTS_API: {config.api}")

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=config.timeout_seconds,
    )

    if response.status_code >= 400:
        raise NarrationAPIError(
            response.status_code, response.text[:500]
        )

    data = response.json()
    audio = ensure_wav(extract_audio(data, config.api))
    return audio, extract_usage(data)


def is_retryable(exc):
    if isinstance(exc, NarrationAPIError):
        return exc.status_code == 429 or exc.status_code >= 500
    return isinstance(exc, (requests.RequestException, NarrationError))


def wav_duration(path):
    try:
        with wave.open(str(path), "rb") as handle:
            return handle.getnframes() / float(handle.getframerate())
    except (wave.Error, OSError) as exc:
        raise NarrationError(f"cannot read WAV file {path}: {exc}") from exc


def generate_shot(
    shot,
    config,
    cache,
    logger,
    force=False,
    dry_run=False,
    narration_dir=NARRATION_DIR,
    retry_config=None,
):
    retry_config = retry_config or load_retry_config()
    key = input_hash(narration_inputs(shot, config))
    output_path = Path(narration_dir) / f"{shot['id']}.wav"
    cached = cache.get("narration", key, ".wav")

    if cached is not None and not force:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(cached, output_path)
        duration = wav_duration(output_path)
        return {
            "shot_id": shot["id"],
            "path": str(output_path),
            "input_hash": key,
            "cache_hit": True,
            "duration_seconds": round(duration, 3),
            "allocated_seconds": shot["duration_seconds"],
            "overflow": duration > shot["duration_seconds"] + 0.05,
            "success": True,
        }

    if dry_run:
        return {
            "shot_id": shot["id"],
            "path": str(output_path),
            "input_hash": key,
            "cache_hit": cached is not None,
            "allocated_seconds": shot["duration_seconds"],
            "dry_run": True,
            "success": True,
        }

    retries = []

    def record_retry(attempt, delay, exc):
        retries.append(
            {
                "attempt": attempt,
                "delay_seconds": delay,
                "error": str(exc),
            }
        )

    started = time.perf_counter()
    try:
        audio, usage = retry_call(
            lambda: synthesize_narration(shot["narration_am"], config),
            attempts=retry_config.attempts,
            base_delay_seconds=retry_config.base_delay_seconds,
            max_delay_seconds=retry_config.max_delay_seconds,
            retry_if=is_retryable,
            on_retry=record_retry,
        )
    except Exception as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        logger.log(
            {
                "stage": "narration",
                "shot_id": shot["id"],
                "provider": "google",
                "model": config.model,
                "params": {
                    "text": shot["narration_am"],
                    "voice": config.voice,
                    "style": config.style,
                    "api": config.api,
                },
                "seed": None,
                "seed_supported": False,
                "input_hash": key,
                "latency_ms": round(latency_ms, 1),
                "cost_usd": None,
                "cost_basis": "request_failed",
                "success": False,
                "error": str(exc),
                "retries": retries,
            }
        )
        raise

    latency_ms = (time.perf_counter() - started) * 1000
    cache.put_bytes("narration", key, ".wav", audio)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(audio)
    duration = wav_duration(output_path)
    cost, cost_basis = estimate_cost(config.model, usage)

    logger.log(
        {
            "stage": "narration",
            "shot_id": shot["id"],
            "provider": "google",
            "model": config.model,
            "params": {
                "text": shot["narration_am"],
                "voice": config.voice,
                "style": config.style,
                "api": config.api,
            },
            "seed": None,
            "seed_supported": False,
            "input_hash": key,
            "latency_ms": round(latency_ms, 1),
            "cost_usd": cost,
            "cost_basis": cost_basis,
            "usage": usage,
            "success": True,
            "error": None,
            "retries": retries,
        }
    )

    return {
        "shot_id": shot["id"],
        "path": str(output_path),
        "input_hash": key,
        "cache_hit": False,
        "duration_seconds": round(duration, 3),
        "allocated_seconds": shot["duration_seconds"],
        "overflow": duration > shot["duration_seconds"] + 0.05,
        "success": True,
    }


def write_report(path, results, shot_ids):
    existing = {}
    report_path = Path(path)
    if report_path.is_file():
        with open(report_path, encoding="utf-8") as handle:
            for entry in json.load(handle):
                existing[entry["shot_id"]] = entry
    for result in results:
        existing[result["shot_id"]] = result
    ordered = [existing[shot_id] for shot_id in shot_ids if shot_id in existing]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(ordered, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate Amharic narration with Gemini TTS."
    )
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--all", action="store_true")
    selection.add_argument("--shot")
    parser.add_argument("--storyboard", default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        if args.storyboard:
            storyboard = load_storyboard(args.storyboard)
        else:
            storyboard = load_storyboard()
    except StoryboardError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1

    shot_ids = [shot["id"] for shot in storyboard["shots"]]
    if args.shot:
        try:
            shots = [shot_by_id(storyboard, args.shot)]
        except StoryboardError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    else:
        shots = storyboard["shots"]

    try:
        config = load_gemini_tts_config(require_key=not args.dry_run)
    except MissingCredentialError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    cache = FileCache(CACHE_DIR)
    logger = RunLogger(RUNS_PATH)
    results = []
    failures = 0

    for shot in shots:
        try:
            result = generate_shot(
                shot,
                config,
                cache,
                logger,
                force=args.force,
                dry_run=args.dry_run,
            )
        except Exception as exc:
            failures += 1
            print(f"{shot['id']}: FAILED {exc}", file=sys.stderr)
            continue

        results.append(result)
        if result.get("dry_run"):
            state = "cached" if result["cache_hit"] else "missing"
            print(
                f"{shot['id']}: dry run, cache {state}, "
                f"hash {result['input_hash'][:12]}"
            )
        elif result["overflow"]:
            print(
                f"{shot['id']}: warning, narration "
                f"{result['duration_seconds']:.2f}s exceeds "
                f"{result['allocated_seconds']:.2f}s"
            )
        else:
            state = "cache" if result["cache_hit"] else "generated"
            print(
                f"{shot['id']}: {state}, "
                f"{result['duration_seconds']:.2f}s / "
                f"{result['allocated_seconds']:.2f}s"
            )

    if results and not args.dry_run:
        write_report(
            NARRATION_DIR / "report.json", results, shot_ids
        )

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
