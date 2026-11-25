import hashlib

from pipeline.hashing import canonical_json, file_sha256, input_hash


def test_canonical_json_ignores_key_order():
    assert canonical_json({"b": 1, "a": 2}) == canonical_json({"a": 2, "b": 1})


def test_input_hash_is_stable_across_key_order():
    assert input_hash({"a": 1, "b": "x"}) == input_hash({"b": "x", "a": 1})


def test_input_hash_changes_when_value_changes():
    assert input_hash({"a": 1}) != input_hash({"a": 2})


def test_input_hash_preserves_amharic():
    assert input_hash({"text": "ትግል"}) == input_hash({"text": "ትግል"})
    assert input_hash({"text": "ትግል"}) != input_hash({"text": "ትግል "})


def test_file_sha256_matches_hashlib(tmp_path):
    path = tmp_path / "sample.bin"
    path.write_bytes(b"hello")
    assert file_sha256(path) == hashlib.sha256(b"hello").hexdigest()
