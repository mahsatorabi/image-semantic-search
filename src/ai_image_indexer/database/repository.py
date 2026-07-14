"""Data access layer for the local SQLite image index."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import numpy as np

from ai_image_indexer.database.schema import (
    ImageRecord,
    init_schema,
    row_to_record,
    utc_now_iso,
)


class ImageRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        init_schema(self._conn)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> ImageRepository:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def get_by_filepath(self, filepath: str) -> ImageRecord | None:
        row = self._conn.execute(
            "SELECT * FROM images WHERE filepath = ?", (filepath,)
        ).fetchone()
        return row_to_record(row) if row else None

    def get_all_with_embeddings(self) -> list[ImageRecord]:
        rows = self._conn.execute(
            "SELECT * FROM images WHERE embedding IS NOT NULL"
        ).fetchall()
        return [row_to_record(r) for r in rows]

    def upsert(self, record: ImageRecord) -> ImageRecord:
        now = utc_now_iso()
        embedding_blob = None
        if record.embedding:
            embedding_blob = np.array(record.embedding, dtype=np.float32).tobytes()

        existing = self.get_by_filepath(record.filepath)
        indexed_at = existing.indexed_at if existing else now

        self._conn.execute(
            """
            INSERT INTO images (
                filepath, filename, file_hash, file_size, file_mtime,
                caption, tags, ocr_text, embedding, indexed_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(filepath) DO UPDATE SET
                filename = excluded.filename,
                file_hash = excluded.file_hash,
                file_size = excluded.file_size,
                file_mtime = excluded.file_mtime,
                caption = excluded.caption,
                tags = excluded.tags,
                ocr_text = excluded.ocr_text,
                embedding = excluded.embedding,
                updated_at = excluded.updated_at
            """,
            (
                record.filepath,
                record.filename,
                record.file_hash,
                record.file_size,
                record.file_mtime,
                record.caption,
                json.dumps(record.tags, ensure_ascii=False),
                record.ocr_text,
                embedding_blob,
                indexed_at,
                now,
            ),
        )
        self._conn.commit()
        return self.get_by_filepath(record.filepath)  # type: ignore[return-value]

    def remove_stale_under_prefix(self, folder_prefix: str, valid_paths: set[str]) -> int:
        """Remove indexed images under *folder_prefix* that no longer exist on disk."""
        prefix = folder_prefix.rstrip("\\/") + "/"
        prefix_alt = folder_prefix.rstrip("\\/") + "\\"
        rows = self._conn.execute(
            """
            SELECT filepath FROM images
            WHERE filepath LIKE ? OR filepath LIKE ?
            """,
            (prefix + "%", prefix_alt + "%"),
        ).fetchall()
        stale = [
            row["filepath"]
            for row in rows
            if row["filepath"] not in valid_paths
        ]
        if not stale:
            return 0
        placeholders = ",".join("?" * len(stale))
        cursor = self._conn.execute(
            f"DELETE FROM images WHERE filepath IN ({placeholders})",
            tuple(stale),
        )
        self._conn.commit()
        return cursor.rowcount

    def stats(self) -> dict[str, int | str]:
        total = self._conn.execute("SELECT COUNT(*) FROM images").fetchone()[0]
        with_embedding = self._conn.execute(
            "SELECT COUNT(*) FROM images WHERE embedding IS NOT NULL"
        ).fetchone()[0]
        db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
        return {
            "total_images": total,
            "with_embeddings": with_embedding,
            "db_size_bytes": db_size,
            "db_path": str(self.db_path),
        }

    def export_all(self) -> list[dict]:
        rows = self._conn.execute("SELECT * FROM images ORDER BY filepath").fetchall()
        return [row_to_record(r).to_dict() for r in rows]
