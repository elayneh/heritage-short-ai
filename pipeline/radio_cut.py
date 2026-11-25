import argparse
import json
import shutil
import subprocess
import sys
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .config import (
    NARRATION_DIR,
    RADIO_CUT_DIR,
    RUNS_PATH,
    STORYBOARD_PATH,
)
from .hashing import input_hash
from .logging_utils import RunLogger
from .storyboard import StoryboardError, load_storyboard

WIDTH = 1080
HEIGHT = 1920
FPS = 30
SAMPLE_RATE = 24000
FONT_EN = Path("/System/Library/Fonts/Supplemental/Arial.ttf")
FONT_AM = Path("/System/Library/Fonts/Supplemental/KefaIII.ttf")


class RadioCutError(RuntimeError):
    pass


def run_ffmpeg(arguments):
    result = subprocess.run(
        ["ffmpeg", *arguments], capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RadioCutError(f"ffmpeg failed: {result.stderr[-2000:]}")
    return result


def wav_duration(path):
    try:
        with wave.open(str(path), "rb") as handle:
            return handle.getnframes() / float(handle.getframerate())
    except (wave.Error, OSError) as exc:
        raise RadioCutError(f"cannot read WAV file {path}: {exc}") from exc


def ffprobe_duration(path):
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RadioCutError(f"ffprobe failed: {result.stderr[-2000:]}")
    return float(result.stdout.strip())


def build_timeline(storyboard, narration_dir, strict=False):
    entries = []
    missing = []
    cursor = 0.0

    for shot in storyboard["shots"]:
        path = Path(narration_dir) / f"{shot['id']}.wav"
        if not path.is_file():
            missing.append(shot["id"])
            continue

        narration_seconds = wav_duration(path)
        allocated_seconds = float(shot["duration_seconds"])
        segment_seconds = max(allocated_seconds, narration_seconds)
        overflow = narration_seconds > allocated_seconds + 0.05

        entries.append(
            {
                "shot_id": shot["id"],
                "path": str(path),
                "narration_seconds": round(narration_seconds, 3),
                "allocated_seconds": allocated_seconds,
                "segment_seconds": round(segment_seconds, 3),
                "start": round(cursor, 3),
                "end": round(cursor + segment_seconds, 3),
                "overflow": overflow,
                "subtitle_en": shot["subtitle_en"],
            }
        )
        cursor += segment_seconds

    if missing:
        raise RadioCutError(
            "missing narration for "
            + ", ".join(missing)
            + ". Run make narration first."
        )

    overflow_shots = [
        entry["shot_id"] for entry in entries if entry["overflow"]
    ]
    if strict and overflow_shots:
        raise RadioCutError(
            "narration exceeds allocated time for "
            + ", ".join(overflow_shots)
            + ". Regenerate with --force or run without --strict."
        )

    return entries, cursor


def write_narration_report(path, entries, total_seconds):
    report = {
        "total_seconds": round(total_seconds, 3),
        "overflow_shots": [
            entry["shot_id"] for entry in entries if entry["overflow"]
        ],
        "shots": entries,
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def build_narration_track(entries, workdir):
    concat_lines = []
    for entry in entries:
        segment = workdir / f"seg_{entry['shot_id']}.wav"
        run_ffmpeg(
            [
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                entry["path"],
                "-af",
                f"aresample={SAMPLE_RATE},"
                f"apad=whole_dur={entry['segment_seconds']:.3f}",
                "-ac",
                "1",
                "-ar",
                str(SAMPLE_RATE),
                "-c:a",
                "pcm_s16le",
                str(segment),
            ]
        )
        concat_lines.append(f"file '{segment.as_posix()}'")

    concat_file = workdir / "concat.txt"
    concat_file.write_text(
        "\n".join(concat_lines) + "\n", encoding="utf-8"
    )
    track = workdir / "narration_track.wav"
    run_ffmpeg(
        [
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            str(track),
        ]
    )
    return track


def build_music(path, duration):
    fade_out_start = max(0.0, duration - 4.0)
    filter_complex = (
        "[0:a]volume=0.5[a0];"
        "[1:a]volume=0.25[a1];"
        "[2:a]volume=0.12[a2];"
        "[a0][a1][a2]amix=inputs=3:duration=longest,"
        "lowpass=f=800,tremolo=f=0.15:d=0.3,"
        f"afade=t=in:d=3,afade=t=out:st={fade_out_start:.3f}:d=4,"
        "volume=0.25[a]"
    )
    run_ffmpeg(
        [
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=110:sample_rate={SAMPLE_RATE}:"
            f"duration={duration:.3f}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=164.81:sample_rate={SAMPLE_RATE}:"
            f"duration={duration:.3f}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=220:sample_rate={SAMPLE_RATE}:"
            f"duration={duration:.3f}",
            "-filter_complex",
            filter_complex,
            "-map",
            "[a]",
            "-ac",
            "1",
            "-ar",
            str(SAMPLE_RATE),
            "-c:a",
            "pcm_s16le",
            str(path),
        ]
    )
    return path


def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if not current or draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def render_subtitle_png(text, path, font_size=44, max_width=920):
    font = ImageFont.truetype(str(FONT_EN), font_size)
    image = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    lines = wrap_text(draw, text, font, max_width)
    line_height = int(font_size * 1.35)
    block_height = line_height * len(lines)
    y = HEIGHT - 230 - block_height

    for line in lines:
        width = draw.textlength(line, font=font)
        x = (WIDTH - width) / 2
        draw.text(
            (x, y),
            line,
            font=font,
            fill=(255, 255, 255, 255),
            stroke_width=3,
            stroke_fill=(0, 0, 0, 230),
        )
        y += line_height

    image.save(path)
    return path


def draw_centered(draw, text, font, y, fill=(255, 255, 255, 255)):
    box = draw.textbbox((0, 0), text, font=font)
    width = box[2] - box[0]
    draw.text(((WIDTH - width) / 2, y), text, font=font, fill=fill)
    return y + (box[3] - box[1])


def render_end_card(path):
    image = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
    draw = ImageDraw.Draw(image)
    title_am = ImageFont.truetype(str(FONT_AM), 104)
    title_en = ImageFont.truetype(str(FONT_EN), 46)
    final_am = ImageFont.truetype(str(FONT_AM), 50)
    final_en = ImageFont.truetype(str(FONT_EN), 34)
    disclosure = ImageFont.truetype(str(FONT_EN), 26)

    draw_centered(draw, "ትግል ለ30", title_am, 560)
    draw_centered(draw, "The Struggle for 30", title_en, 730)
    draw_centered(draw, "የእኔ ጉዞ አበቃ። የእሱ ትግል ግን ቀጥሏል።", final_am, 1020)
    draw_centered(
        draw,
        "My journey ended. His struggle continued.",
        final_en,
        1110,
    )
    draw_centered(
        draw,
        "AI-generated film. Characters and appearances are fictional.",
        disclosure,
        1700,
        fill=(190, 190, 190, 255),
    )
    image.save(path)
    return path


def build_video(
    entries,
    workdir,
    out_path,
    narration_track,
    music_path,
    total_seconds,
    fps=FPS,
):
    overlays = []
    for entry in entries[:-1]:
        subtitle_path = workdir / f"sub_{entry['shot_id']}.png"
        render_subtitle_png(entry["subtitle_en"], subtitle_path)
        overlays.append(
            (subtitle_path, entry["start"], entry["end"])
        )

    end_card = workdir / "end_card.png"
    render_end_card(end_card)
    overlays.append(
        (end_card, entries[-1]["start"], total_seconds)
    )

    command = [
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"color=c=black:s={WIDTH}x{HEIGHT}:r={fps}:"
        f"d={total_seconds:.3f}",
    ]
    for overlay_path, _, _ in overlays:
        command += [
            "-loop",
            "1",
            "-framerate",
            "1",
            "-t",
            f"{total_seconds:.3f}",
            "-i",
            str(overlay_path),
        ]

    command += ["-i", str(narration_track), "-i", str(music_path)]

    filter_parts = []
    previous = "[0:v]"
    for index, (_, start, end) in enumerate(overlays, start=1):
        output = f"[v{index}]"
        filter_parts.append(
            f"{previous}[{index}:v]overlay=0:0:"
            f"enable='between(t,{start:.3f},{end:.3f})'{output}"
        )
        previous = output
    filter_parts.append(f"{previous}format=yuv420p[vout]")

    narration_index = 1 + len(overlays)
    music_index = narration_index + 1
    filter_parts.append(f"[{narration_index}:a]volume=1.0[narr]")
    filter_parts.append(f"[{music_index}:a]volume=0.12[music]")
    filter_parts.append(
        "[narr][music]amix=inputs=2:duration=longest:"
        "dropout_transition=0[aout]"
    )

    command += [
        "-filter_complex",
        ";".join(filter_parts),
        "-map",
        "[vout]",
        "-map",
        "[aout]",
        "-t",
        f"{total_seconds:.3f}",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(out_path),
    ]

    run_ffmpeg(command)
    return out_path


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build the black-screen radio cut with narration and subtitles."
    )
    parser.add_argument("--storyboard", default=str(STORYBOARD_PATH))
    parser.add_argument("--narration-dir", default=str(NARRATION_DIR))
    parser.add_argument(
        "--out", default=str(RADIO_CUT_DIR / "radio_cut.mp4")
    )
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--keep-workdir", action="store_true")
    args = parser.parse_args(argv)

    try:
        storyboard = load_storyboard(args.storyboard)
    except StoryboardError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1

    if storyboard["aspect_ratio"] != "9:16":
        print(
            "FAILED: the radio cut currently renders 9:16 only",
            file=sys.stderr,
        )
        return 1

    fps = int(storyboard["fps"])
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    workdir = out_path.parent / "work"
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)

    try:
        entries, total_seconds = build_timeline(
            storyboard, args.narration_dir, strict=args.strict
        )
        write_narration_report(
            out_path.parent / "narration_report.json",
            entries,
            total_seconds,
        )

        for entry in entries:
            if entry["overflow"]:
                print(
                    f"{entry['shot_id']}: warning, narration "
                    f"{entry['narration_seconds']:.2f}s exceeds "
                    f"{entry['allocated_seconds']:.2f}s",
                    file=sys.stderr,
                )

        narration_track = build_narration_track(entries, workdir)
        music_path = build_music(workdir / "placeholder_music.wav", total_seconds)
        build_video(
            entries,
            workdir,
            out_path,
            narration_track,
            music_path,
            total_seconds,
            fps=fps,
        )
    except RadioCutError as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1
    finally:
        if not args.keep_workdir:
            shutil.rmtree(workdir, ignore_errors=True)

    try:
        measured = ffprobe_duration(out_path)
    except RadioCutError as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1

    RunLogger(RUNS_PATH).log(
        {
            "stage": "radio_cut",
            "shot_id": None,
            "provider": "local",
            "model": "ffmpeg",
            "params": {
                "shots": len(entries),
                "width": WIDTH,
                "height": HEIGHT,
                "fps": fps,
            },
            "seed": None,
            "seed_supported": False,
            "input_hash": input_hash(storyboard),
            "latency_ms": None,
            "cost_usd": 0.0,
            "cost_basis": "local_compute",
            "success": True,
            "error": None,
        }
    )

    print(f"Wrote {out_path}")
    print(
        f"Duration {measured:.2f}s, "
        f"{len(entries)} shots"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
