from pipeline.cache import FileCache


def test_put_and_get_bytes(tmp_path):
    cache = FileCache(tmp_path)
    cache.put_bytes("narration", "abc", ".wav", b"data")
    assert cache.get("narration", "abc", ".wav").read_bytes() == b"data"


def test_missing_key_returns_none(tmp_path):
    cache = FileCache(tmp_path)
    assert cache.get("narration", "missing", ".wav") is None


def test_changed_key_misses(tmp_path):
    cache = FileCache(tmp_path)
    cache.put_bytes("narration", "first", ".wav", b"data")
    assert cache.get("narration", "second", ".wav") is None


def test_put_file_copies_source(tmp_path):
    source = tmp_path / "source.bin"
    source.write_bytes(b"payload")
    cache = FileCache(tmp_path / "cache")
    path = cache.put_file("narration", "key", ".bin", source)
    assert path.read_bytes() == b"payload"
    assert source.read_bytes() == b"payload"


def test_empty_file_is_not_a_cache_hit(tmp_path):
    cache = FileCache(tmp_path)
    path = cache.path_for("narration", "empty", ".wav")
    path.parent.mkdir(parents=True)
    path.write_bytes(b"")
    assert cache.get("narration", "empty", ".wav") is None
