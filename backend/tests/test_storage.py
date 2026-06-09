import os
from pathlib import Path

import pytest

from service.core import storage


@pytest.fixture(autouse=True)
def isolated_upload_root(tmp_path, monkeypatch):
    """Override UPLOAD_ROOT to a temp directory for every test."""
    monkeypatch.setattr(storage, "UPLOAD_ROOT", tmp_path)


def test_save_temp_upload_creates_file():
    data = b"hello world"
    rel = storage.save_temp_upload(data, "notes.txt")

    assert rel.startswith("temp/")
    assert rel.endswith(".txt")

    full = storage.UPLOAD_ROOT / rel
    assert full.exists()
    assert full.read_bytes() == data


def test_save_temp_upload_preserves_extension():
    rel = storage.save_temp_upload(b"data", "document.pdf")
    assert rel.endswith(".pdf")


def test_move_to_final_moves_file():
    rel = storage.save_temp_upload(b"content", "file.txt")
    final_rel = storage.move_to_final(rel, 42, "file.txt")

    assert final_rel.startswith("42/")
    assert final_rel.endswith("file.txt")

    assert not (storage.UPLOAD_ROOT / rel).exists()
    assert (storage.UPLOAD_ROOT / final_rel).exists()
    assert (storage.UPLOAD_ROOT / final_rel).read_bytes() == b"content"


def test_move_to_final_handles_duplicate_names():
    rel1 = storage.save_temp_upload(b"first", "file.txt")
    rel2 = storage.save_temp_upload(b"second", "file.txt")

    storage.move_to_final(rel1, 1, "file.txt")
    final2 = storage.move_to_final(rel2, 1, "file.txt")

    assert final2 == "1/file_1.txt"
    assert (storage.UPLOAD_ROOT / final2).read_bytes() == b"second"


def test_move_to_final_missing_temp_raises():
    with pytest.raises(FileNotFoundError):
        storage.move_to_final("temp/nonexistent.txt", 1, "file.txt")


def test_resolve_file_path_returns_absolute():
    rel = storage.save_temp_upload(b"x", "a.txt")
    resolved = storage.resolve_file_path(rel)
    assert resolved == (storage.UPLOAD_ROOT / rel).resolve()


def test_resolve_file_path_traversal_raises():
    with pytest.raises(ValueError, match="path traversal"):
        storage.resolve_file_path("../../../etc/passwd")


def test_resolve_file_path_traversal_with_null_bytes_raises():
    with pytest.raises(ValueError, match="path traversal"):
        storage.resolve_file_path("foo\x00bar")
