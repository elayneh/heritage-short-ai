import json

from jsonschema import Draft202012Validator

from .config import SCHEMA_PATH, STORYBOARD_PATH


class StoryboardError(ValueError):
    pass


def read_json(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise StoryboardError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise StoryboardError(f"invalid JSON in {path}: {exc}") from exc


def semantic_errors(data):
    errors = []
    shots = data["shots"]
    ids = [shot["id"] for shot in shots]

    duplicates = sorted({shot_id for shot_id in ids if ids.count(shot_id) > 1})
    if duplicates:
        errors.append(f"duplicate shot ids: {', '.join(duplicates)}")

    character_ids = set(data["characters"])
    vehicle_ids = set(data["vehicles"])

    for shot in shots:
        for ref in shot["character_refs"]:
            if ref not in character_ids:
                errors.append(f"{shot['id']}: unknown character ref {ref}")
        for ref in shot["vehicle_refs"]:
            if ref not in vehicle_ids:
                errors.append(f"{shot['id']}: unknown vehicle ref {ref}")

    computed_total = sum(shot["duration_seconds"] for shot in shots)
    declared_total = data["total_duration_seconds"]
    if abs(computed_total - declared_total) > 0.01:
        errors.append(
            "total_duration_seconds "
            f"{declared_total} does not match shot total {computed_total}"
        )
    if not 60 <= computed_total <= 90:
        errors.append(
            f"shot total {computed_total} is outside 60-90 seconds"
        )

    return errors


def validate_storyboard(data, schema):
    errors = []
    validator = Draft202012Validator(schema)
    for error in sorted(
        validator.iter_errors(data), key=lambda item: list(item.path)
    ):
        location = ".".join(str(part) for part in error.path) or "<root>"
        errors.append(f"{location}: {error.message}")

    if errors:
        return errors

    return semantic_errors(data)


def load_storyboard(path=STORYBOARD_PATH, schema_path=SCHEMA_PATH):
    data = read_json(path)
    schema = read_json(schema_path)
    errors = validate_storyboard(data, schema)
    if errors:
        raise StoryboardError("\n".join(errors))
    return data


def shot_by_id(data, shot_id):
    for shot in data["shots"]:
        if shot["id"] == shot_id:
            return shot
    raise StoryboardError(f"unknown shot id: {shot_id}")
