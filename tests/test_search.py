"""Tests for semantic search engine."""

import numpy as np

from ai_image_indexer.database.schema import ImageRecord, utc_now_iso
from ai_image_indexer.search.engine import SearchEngine


class FakeAIClient:
    def embed_text(self, text: str) -> list[float]:
        if "cat" in text.lower():
            return [1.0, 0.0, 0.0]
        if "dog" in text.lower():
            return [0.0, 1.0, 0.0]
        return [0.5, 0.5, 0.0]


class FakeRepo:
    def __init__(self, records: list[ImageRecord]) -> None:
        self._records = records

    def get_all_with_embeddings(self) -> list[ImageRecord]:
        return self._records


def _record(caption: str, embedding: list[float]) -> ImageRecord:
    now = utc_now_iso()
    return ImageRecord(
        id=1,
        filepath=f"/tmp/{caption}.jpg",
        filename=f"{caption}.jpg",
        file_hash="x",
        file_size=1,
        file_mtime=1.0,
        caption=caption,
        tags=[],
        ocr_text="",
        embedding=embedding,
        indexed_at=now,
        updated_at=now,
    )


def test_search_ranks_by_similarity():
    records = [
        _record("A cat sleeping", [1.0, 0.0, 0.0]),
        _record("A dog running", [0.0, 1.0, 0.0]),
    ]
    engine = SearchEngine(FakeRepo(records), FakeAIClient())  # type: ignore[arg-type]
    results = engine.search("cat", limit=2)
    assert len(results) == 1
    assert "cat" in results[0].record.caption.lower()
    assert results[0].score == 1.0


def test_search_threshold_filters_irrelevant():
    records = [
        _record("A cat sleeping", [1.0, 0.0, 0.0]),
        _record("A dog running", [0.0, 1.0, 0.0]),
        _record("A mountain view", [0.5, 0.5, 0.0]),
    ]
    engine = SearchEngine(FakeRepo(records), FakeAIClient())  # type: ignore[arg-type]
    results = engine.search("cat", limit=10, min_score=0.5)
    assert all(r.score >= 0.5 for r in results)
    assert "cat" in results[0].record.caption.lower()


def test_search_low_threshold_returns_more():
    records = [
        _record("A cat sleeping", [1.0, 0.0, 0.0]),
        _record("A dog running", [0.0, 1.0, 0.0]),
    ]
    engine = SearchEngine(FakeRepo(records), FakeAIClient())  # type: ignore[arg-type]
    results = engine.search("cat", limit=10, min_score=0.0)
    assert len(results) == 2


def test_search_empty_query():
    engine = SearchEngine(FakeRepo([]), FakeAIClient())  # type: ignore[arg-type]
    assert engine.search("") == []
    assert engine.search("   ") == []
