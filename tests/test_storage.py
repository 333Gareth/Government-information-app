import json

from gov_intel.storage import load_json, save_json


def test_save_then_load_roundtrip(tmp_path):
    p = tmp_path / "data.json"
    save_json(p, {"a": 1, "b": [1, 2, 3]})
    assert load_json(p, default=None) == {"a": 1, "b": [1, 2, 3]}


def test_load_missing_file_returns_default(tmp_path):
    p = tmp_path / "missing.json"
    assert load_json(p, default={"x": 1}) == {"x": 1}


def test_load_corrupt_file_returns_default(tmp_path):
    p = tmp_path / "corrupt.json"
    p.write_text("{not valid json", encoding="utf-8")
    assert load_json(p, default=[]) == []


def test_save_creates_parent_directories(tmp_path):
    p = tmp_path / "nested" / "dir" / "data.json"
    save_json(p, {"ok": True})
    assert p.exists()
    assert json.loads(p.read_text()) == {"ok": True}


def test_save_does_not_leave_temp_files_behind(tmp_path):
    p = tmp_path / "data.json"
    save_json(p, {"a": 1})
    leftovers = [f for f in tmp_path.iterdir() if f.name.startswith(".tmp_")]
    assert leftovers == []


def test_save_overwrites_existing_file_atomically(tmp_path):
    p = tmp_path / "data.json"
    save_json(p, {"version": 1})
    save_json(p, {"version": 2})
    assert load_json(p, default=None) == {"version": 2}
