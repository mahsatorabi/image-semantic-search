"""Tests for the image folder scanner."""

from pathlib import Path

import pytest

from ai_image_indexer.scanner.scanner import is_image_file, needs_reindex, scan_folder


def test_is_image_file():
    assert is_image_file(Path("photo.jpg"))
    assert is_image_file(Path("photo.JPEG"))
    assert not is_image_file(Path("document.pdf"))


def test_scan_folder(tmp_path: Path):
    (tmp_path / "a.jpg").write_bytes(b"\xff\xd8\xff fake jpeg")
    (tmp_path / "b.png").write_bytes(b"\x89PNG fake")
    (tmp_path / "skip.txt").write_text("not an image")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.webp").write_bytes(b"RIFF fake webp")

    results = scan_folder(tmp_path)
    filenames = {r.filename for r in results}
    assert filenames == {"a.jpg", "b.png", "c.webp"}


def test_scan_folder_not_found():
    with pytest.raises(FileNotFoundError):
        scan_folder(Path("/nonexistent/path/xyz"))


def test_needs_reindex():
    from ai_image_indexer.scanner.scanner import ScannedImage

    img = ScannedImage(
        filepath=Path("/tmp/a.jpg"),
        filename="a.jpg",
        file_hash="abc",
        file_size=100,
        file_mtime=1.0,
    )
    assert needs_reindex(img, None, None, None) is True
    assert needs_reindex(img, "abc", 1.0, 100) is False
    assert needs_reindex(img, "different", 1.0, 100) is True
