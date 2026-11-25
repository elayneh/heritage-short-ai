import os
import tempfile
from pathlib import Path


class FileCache:
    def __init__(self, root):
        self.root = Path(root)

    def path_for(self, stage, key, suffix):
        return self.root / stage / f"{key}{suffix}"

    def get(self, stage, key, suffix):
        path = self.path_for(stage, key, suffix)
        if path.is_file() and path.stat().st_size > 0:
            return path
        return None

    def put_bytes(self, stage, key, suffix, data):
        path = self.path_for(stage, key, suffix)
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp_name = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(data)
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        return path

    def put_file(self, stage, key, suffix, source):
        path = self.path_for(stage, key, suffix)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f".tmp-{path.name}")
        with open(source, "rb") as source_stream, open(
            temp_path, "wb"
        ) as target_stream:
            for chunk in iter(lambda: source_stream.read(1024 * 1024), b""):
                target_stream.write(chunk)
        os.replace(temp_path, path)
        return path
