import base64
import io
import json
import wave

import pytest

from pipeline.cache import FileCache
from pipeline.config import GeminiTTSConfig, RetryConfig
from pipeline.hashing import input_hash
from pipeline.logging_utils import RunLogger
from pipeline.narration import (
    NarrationAPIError,
    build_generate_content_payload,
    build_interactions_payload,
    ensure_wav,
    extract_audio,
    generate_shot,
    narration_inputs,
    synthesize_narration,
)


def make_config(**overrides):
    values = {
        "api_key": "test-key",
        "model": "gemini-3.8-flash-tts",
        "voice": "Charon",
        "style": "calm, reflective",
        "api": "interactions",
        "base_url": "https://example.invalid/v1beta",
        "timeout_seconds": 1.0,
    }
    values.update(overrides)
    return GeminiTTSConfig(**values)


def make_shot(**overrides):
    values = {
        "id": "S01",
        "duration_seconds": 6,
        "narration_am": "ሰላም",
    }
    values.update(overrides)
    return values


def make_wav(seconds):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(24000)
        handle.writeframes(b"\x00\x00" * int(24000 * seconds))
    return buffer.getvalue()


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self.payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self.payload


def test_interactions_payload_shape():
    payload = build_interactions_payload(
        "ሰላም", "gemini-3.8-flash-tts", "Charon", "calm"
    )
    content = payload["input"][0]["content"][0]
    assert payload["model"] == "gemini-3.8-flash-tts"
    assert content["text"] == "ሰላም"
    assert content["annotations"][0]["style"] == "calm"
    assert payload["generation_config"]["speech_config"][0]["voice"] == "Charon"
    assert payload["response_format"] == {"type": "audio"}


def test_generate_content_payload_shape():
    payload = build_generate_content_payload("ሰላም", "Kore", "warm")
    assert payload["contents"][0]["parts"][0]["text"] == "warm style: ሰላም"
    assert payload["generationConfig"]["responseModalities"] == ["AUDIO"]
    voice = payload["generationConfig"]["speechConfig"]["voiceConfig"]
    assert voice["prebuiltVoiceConfig"]["voiceName"] == "Kore"


def test_extract_interactions_audio():
    raw = b"RIFF-test"
    data = {
        "steps": [
            {
                "type": "model_output",
                "content": [
                    {
                        "type": "audio",
                        "data": base64.b64encode(raw).decode("ascii"),
                    }
                ],
            }
        ]
    }
    assert extract_audio(data, "interactions") == raw


def test_extract_generate_content_audio():
    raw = b"pcm-test"
    data = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "inlineData": {
                                "data": base64.b64encode(raw).decode("ascii")
                            }
                        }
                    ]
                }
            }
        ]
    }
    assert extract_audio(data, "generateContent") == raw


def test_ensure_wav_wraps_raw_pcm():
    pcm = b"\x00\x00" * 100
    wav = ensure_wav(pcm)
    assert wav[:4] == b"RIFF"
    with wave.open(io.BytesIO(wav), "rb") as handle:
        assert handle.getnchannels() == 1
        assert handle.getframerate() == 24000
        assert handle.getnframes() == 100


def test_narration_hash_changes_with_text():
    config = make_config()
    first = narration_inputs(make_shot(narration_am="one"), config)
    second = narration_inputs(make_shot(narration_am="two"), config)
    assert input_hash(first) != input_hash(second)


def test_narration_hash_changes_with_voice():
    first = narration_inputs(make_shot(), make_config(voice="Charon"))
    second = narration_inputs(make_shot(), make_config(voice="Kore"))
    assert input_hash(first) != input_hash(second)


def test_generate_shot_uses_cache(tmp_path, monkeypatch):
    calls = {"count": 0}

    def fake_synthesize(text, config):
        calls["count"] += 1
        return make_wav(1.0), {
            "input_tokens": 10,
            "output_tokens": 20,
        }

    monkeypatch.setattr(
        "pipeline.narration.synthesize_narration", fake_synthesize
    )

    cache = FileCache(tmp_path / "cache")
    logger = RunLogger(tmp_path / "runs.jsonl")
    config = make_config()
    retry = RetryConfig(1, 0.0, 0.0)

    first = generate_shot(
        make_shot(),
        config,
        cache,
        logger,
        narration_dir=tmp_path / "out",
        retry_config=retry,
    )
    second = generate_shot(
        make_shot(),
        config,
        cache,
        logger,
        narration_dir=tmp_path / "out",
        retry_config=retry,
    )

    assert calls["count"] == 1
    assert first["cache_hit"] is False
    assert second["cache_hit"] is True
    assert first["input_hash"] == second["input_hash"]
    assert first["overflow"] is False


def test_generate_shot_flags_overflow(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "pipeline.narration.synthesize_narration",
        lambda text, config: (make_wav(7.0), None),
    )
    result = generate_shot(
        make_shot(),
        make_config(),
        FileCache(tmp_path / "cache"),
        RunLogger(tmp_path / "runs.jsonl"),
        narration_dir=tmp_path / "out",
        retry_config=RetryConfig(1, 0.0, 0.0),
    )
    assert result["overflow"] is True


def test_generate_shot_failure_is_logged(tmp_path, monkeypatch):
    def fake_synthesize(text, config):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "pipeline.narration.synthesize_narration", fake_synthesize
    )
    log_path = tmp_path / "runs.jsonl"

    with pytest.raises(RuntimeError):
        generate_shot(
            make_shot(),
            make_config(),
            FileCache(tmp_path / "cache"),
            RunLogger(log_path),
            narration_dir=tmp_path / "out",
            retry_config=RetryConfig(1, 0.0, 0.0),
        )

    entry = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
    assert entry["success"] is False
    assert entry["error"] == "boom"
    assert entry["cost_usd"] is None


def test_synthesize_puts_key_in_header_not_body(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return FakeResponse(
            200,
            {
                "steps": [
                    {
                        "type": "model_output",
                        "content": [
                            {
                                "type": "audio",
                                "data": base64.b64encode(
                                    make_wav(0.2)
                                ).decode("ascii"),
                            }
                        ],
                    }
                ]
            },
        )

    monkeypatch.setattr("pipeline.narration.requests.post", fake_post)
    audio, usage = synthesize_narration("ሰላም", make_config())

    assert captured["headers"]["x-goog-api-key"] == "test-key"
    assert "api_key" not in captured["json"]
    assert audio[:4] == b"RIFF"
    assert usage is None


def test_synthesize_raises_on_http_error(monkeypatch):
    monkeypatch.setattr(
        "pipeline.narration.requests.post",
        lambda *args, **kwargs: FakeResponse(401, {"error": "bad key"}),
    )

    with pytest.raises(NarrationAPIError) as info:
        synthesize_narration("ሰላም", make_config())

    assert info.value.status_code == 401
