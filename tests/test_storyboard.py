import copy

import pytest

from pipeline.config import SCHEMA_PATH, STORYBOARD_PATH
from pipeline.storyboard import (
    StoryboardError,
    load_storyboard,
    read_json,
    validate_storyboard,
)


@pytest.fixture
def schema():
    return read_json(SCHEMA_PATH)


@pytest.fixture
def storyboard():
    return read_json(STORYBOARD_PATH)


def test_real_storyboard_is_valid(schema, storyboard):
    assert validate_storyboard(storyboard, schema) == []


def test_load_storyboard_returns_eleven_shots():
    data = load_storyboard(STORYBOARD_PATH)
    assert len(data["shots"]) == 11
    assert data["total_duration_seconds"] == 88


def test_duplicate_shot_ids_fail(schema, storyboard):
    data = copy.deepcopy(storyboard)
    data["shots"][1]["id"] = data["shots"][0]["id"]
    errors = validate_storyboard(data, schema)
    assert any("duplicate shot ids" in error for error in errors)


def test_duration_mismatch_fails(schema, storyboard):
    data = copy.deepcopy(storyboard)
    data["total_duration_seconds"] = 80
    errors = validate_storyboard(data, schema)
    assert any("does not match shot total" in error for error in errors)


def test_total_outside_range_fails(schema, storyboard):
    data = copy.deepcopy(storyboard)
    data["total_duration_seconds"] = 45
    errors = validate_storyboard(data, schema)
    assert errors


def test_unknown_reference_fails(schema, storyboard):
    data = copy.deepcopy(storyboard)
    data["shots"][0]["character_refs"].append("CH_UNKNOWN")
    errors = validate_storyboard(data, schema)
    assert any("unknown character ref CH_UNKNOWN" in error for error in errors)


def test_too_few_shots_fail(schema, storyboard):
    data = copy.deepcopy(storyboard)
    data["shots"] = data["shots"][:7]
    errors = validate_storyboard(data, schema)
    assert errors


def test_load_storyboard_raises_on_invalid_file(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(StoryboardError):
        load_storyboard(path)
