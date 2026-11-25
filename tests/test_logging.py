import json

from pipeline.logging_utils import RunLogger


def read_lines(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]


def test_logger_appends_jsonl(tmp_path):
    path = tmp_path / "runs.jsonl"
    logger = RunLogger(path)
    logger.log({"stage": "narration", "shot_id": "S01", "success": True})
    logger.log({"stage": "narration", "shot_id": "S02", "success": False})

    lines = read_lines(path)
    assert len(lines) == 2
    assert lines[0]["stage"] == "narration"
    assert lines[0]["shot_id"] == "S01"
    assert lines[1]["success"] is False
    assert "timestamp" in lines[0]


def test_logger_preserves_amharic(tmp_path):
    path = tmp_path / "runs.jsonl"
    RunLogger(path).log({"text": "ትግል ለ30"})
    assert "ትግል ለ30" in path.read_text(encoding="utf-8")


def test_logger_does_not_invent_credential_fields(tmp_path):
    path = tmp_path / "runs.jsonl"
    entry = RunLogger(path).log({"stage": "narration"})
    assert "api_key" not in entry
    assert "authorization" not in entry
