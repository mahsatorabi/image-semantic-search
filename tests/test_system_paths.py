"""Tests for default system image folder discovery."""

from pathlib import Path

from ai_image_indexer.scanner.system_paths import default_system_image_roots, resolve_scan_roots


def test_resolve_scan_roots_uses_explicit_paths(tmp_path: Path):
    photos = tmp_path / "photos"
    photos.mkdir()
    roots = resolve_scan_roots([photos])
    assert roots == [photos.resolve()]


def test_resolve_scan_roots_skips_missing_paths(tmp_path: Path):
    missing = tmp_path / "does-not-exist"
    roots = resolve_scan_roots([missing])
    assert roots == [] or all(path.exists() for path in roots)


def test_default_system_image_roots_returns_existing_dirs():
    roots = default_system_image_roots()
    assert all(path.is_dir() for path in roots)
