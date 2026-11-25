import argparse
import sys

from .config import STORYBOARD_PATH
from .storyboard import StoryboardError, load_storyboard


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Validate a storyboard before any model call."
    )
    parser.add_argument(
        "path", nargs="?", default=str(STORYBOARD_PATH)
    )
    args = parser.parse_args(argv)

    try:
        storyboard = load_storyboard(args.path)
    except StoryboardError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1

    shots = storyboard["shots"]
    print(
        f"OK: {len(shots)} shots, "
        f"{storyboard['total_duration_seconds']} seconds, "
        f"{storyboard['aspect_ratio']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
