import wave

import pytest

from pipeline.radio_cut import (
    RadioCutError,
    build_timeline,
    wrap_text,
)
from pipeline.storyboard import load_storyboard


def write_wav(path, seconds):
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(24000)
        handle.writeframes(b"\x00\x00" * int(24000 * seconds))


@pytest.fixture
def storyboard():
    return load_storyboard()


def test_timeline_pads_short_narration_and_flags_long(storyboard, tmp_path):
    for shot in storyboard["shots"]:
        offset = 1 if shot["id"] == "S05" else -1
        write_wav(tmp_path / f"{shot['id']}.wav", shot["duration_seconds"] + offset)

    entries, total = build_timeline(storyboard, tmp_path)

    assert len(entries) == 11
    first = entries[0]
    assert first["segment_seconds"] == first["allocated_seconds"]
    assert first["overflow"] is False

    shot_five = next(entry for entry in entries if entry["shot_id"] == "S05")
    assert shot_five["overflow"] is True
    assert shot_five["segment_seconds"] == shot_five["narration_seconds"]

    assert total == pytest.approx(
        sum(entry["segment_seconds"] for entry in entries)
    )


def test_timeline_is_contiguous(storyboard, tmp_path):
    for shot in storyboard["shots"]:
        write_wav(tmp_path / f"{shot['id']}.wav", 0.5)

    entries, _ = build_timeline(storyboard, tmp_path)

    for previous, current in zip(entries, entries[1:]):
        assert previous["end"] == current["start"]


def test_missing_narration_fails(storyboard, tmp_path):
    with pytest.raises(RadioCutError, match="missing narration"):
        build_timeline(storyboard, tmp_path)


def test_strict_mode_rejects_overflow(storyboard, tmp_path):
    for shot in storyboard["shots"]:
        write_wav(tmp_path / f"{shot['id']}.wav", shot["duration_seconds"] + 1)

    with pytest.raises(RadioCutError, match="exceeds allocated time"):
        build_timeline(storyboard, tmp_path, strict=True)


def test_wrap_text_splits_long_lines():
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.truetype(
        "/System/Library/Fonts/Supplemental/Arial.ttf", 40
    )
    draw = ImageDraw.Draw(Image.new("RGBA", (100, 100)))
    lines = wrap_text(
        draw,
        "one two three four five six seven eight",
        font,
        120,
    )
    assert len(lines) > 1
    assert " ".join(lines) == "one two three four five six seven eight"
