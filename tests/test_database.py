"""Tests for SQLite repository."""

import json
from pathlib import Path

import numpy as np

from ai_image_indexer.database.repository import ImageRepository
from ai_image_indexer.database.schema import ImageRecord, utc_now_iso


def _sample_record(filepath: str = "/tmp/test.jpg") -> ImageRecord:
    now = utc_now_iso()
    return ImageRecord(
        id=None,
        filepath=filepath,
        filename="test.jpg",
        file_hash="hash123",
        file_size=1024,
        file_mtime=1234567890.0,
        caption="A red cat on a sofa",
        tags=["cat", "sofa", "red"],
        ocr_text="",
        embedding=[0.1, 0.2, 0.3],
        indexed_at=now,
        updated_at=now,
    )


def test_upsert_and_get(tmp_path: Path):
    db_path = tmp_path / "test.db"
    with ImageRepository(db_path) as repo:
        record = _sample_record()
        repo.upsert(record)
        fetched = repo.get_by_filepath(record.filepath)
        assert fetched is not None
        assert fetched.caption == "A red cat on a sofa"
        assert fetched.tags == ["cat", "sofa", "red"]
        assert fetched.embedding == [0.1, 0.2, 0.3]


def test_stats(tmp_path: Path):
    db_path = tmp_path / "test.db"
    with ImageRepository(db_path) as repo:
        repo.upsert(_sample_record("/a.jpg"))
        repo.upsert(_sample_record("/b.jpg"))
        stats = repo.stats()
        assert stats["total_images"] == 2


def test_remove_stale_under_prefix(tmp_path: Path):
    db_path = tmp_path / "test.db"
    folder = tmp_path / "photos"
    folder.mkdir()
    with ImageRepository(db_path) as repo:
        repo.upsert(_sample_record(str(folder / "keep.jpg")))
        repo.upsert(_sample_record(str(folder / "gone.jpg")))
        repo.upsert(_sample_record(str(tmp_path / "other" / "x.jpg").replace("\\", "/")))
        valid = {str(folder / "keep.jpg")}
        removed = repo.remove_stale_under_prefix(str(folder), valid)
        assert removed == 1
        assert repo.get_by_filepath(str(folder / "keep.jpg")) is not None
        assert repo.get_by_filepath(str(folder / "gone.jpg")) is None


def test_export_all(tmp_path: Path):
    db_path = tmp_path / "test.db"
    with ImageRepository(db_path) as repo:
        repo.upsert(_sample_record())
        exported = repo.export_all()
        assert len(exported) == 1
        assert exported[0]["caption"] == "A red cat on a sofa"
