import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

STORYBOARD_PATH = ROOT / "storyboard.json"
SCHEMA_PATH = ROOT / "schema" / "storyboard.schema.json"
OUTPUTS_DIR = ROOT / "outputs"
NARRATION_DIR = OUTPUTS_DIR / "narration"
RADIO_CUT_DIR = OUTPUTS_DIR / "radio_cut"
CACHE_DIR = ROOT / ".cache"
RUNS_PATH = ROOT / "runs.jsonl"


class MissingCredentialError(RuntimeError):
    pass


@dataclass(frozen=True)
class GeminiTTSConfig:
    api_key: str
    model: str
    voice: str
    style: str
    api: str
    base_url: str
    timeout_seconds: float


@dataclass(frozen=True)
class RetryConfig:
    attempts: int
    base_delay_seconds: float
    max_delay_seconds: float


def load_gemini_tts_config(require_key=True):
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if require_key and not api_key:
        raise MissingCredentialError("GEMINI_API_KEY is not set")

    api = os.getenv("GEMINI_TTS_API", "interactions").strip()
    default_model = (
        "gemini-3.8-flash-tts"
        if api == "interactions"
        else "gemini-2.5-flash-preview-tts"
    )

    return GeminiTTSConfig(
        api_key=api_key,
        model=os.getenv("GEMINI_TTS_MODEL", default_model).strip(),
        voice=os.getenv("GEMINI_TTS_VOICE", "Charon").strip(),
        style=os.getenv(
            "GEMINI_TTS_STYLE", "calm, reflective, conversational"
        ).strip(),
        api=api,
        base_url=os.getenv(
            "GEMINI_API_BASE",
            "https://generativelanguage.googleapis.com/v1beta",
        ).rstrip("/"),
        timeout_seconds=float(os.getenv("GEMINI_TIMEOUT_SECONDS", "120")),
    )


def load_retry_config():
    return RetryConfig(
        attempts=int(os.getenv("RETRY_ATTEMPTS", "3")),
        base_delay_seconds=float(os.getenv("RETRY_BASE_DELAY_SECONDS", "1.0")),
        max_delay_seconds=float(os.getenv("RETRY_MAX_DELAY_SECONDS", "20.0")),
    )
