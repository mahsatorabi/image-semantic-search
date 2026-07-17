"""Semantic search over indexed image embeddings."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ai_image_indexer.cloudflare.client import CloudflareAIClient
from ai_image_indexer.database.repository import ImageRepository
from ai_image_indexer.database.schema import ImageRecord


@dataclass
class SearchResult:
    record: ImageRecord
    score: float


class SearchEngine:
    def __init__(self, repo: ImageRepository, ai_client: CloudflareAIClient) -> None:
        self.repo = repo
        self.ai_client = ai_client

    def search(
        self, query: str, *, limit: int = 10, min_score: float = 0.25
    ) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []

        query_embedding = np.array(self.ai_client.embed_text(query), dtype=np.float32)
        query_norm = np.linalg.norm(query_embedding)
        if query_norm == 0:
            return []

        records = self.repo.get_all_with_embeddings()
        if not records:
            return []

        scored: list[SearchResult] = []
        for record in records:
            if not record.embedding:
                continue
            vec = np.array(record.embedding, dtype=np.float32)
            vec_norm = np.linalg.norm(vec)
            if vec_norm == 0:
                continue
            score = float(np.dot(query_embedding, vec) / (query_norm * vec_norm))
            if score >= min_score:
                scored.append(SearchResult(record=record, score=score))

        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:limit]
