import json
from datetime import datetime, timezone
from pathlib import Path


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class RunLogger:
    def __init__(self, path):
        self.path = Path(path)

    def log(self, record):
        entry = {"timestamp": utc_now()}
        entry.update(record)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry
