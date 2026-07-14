"""SQLite schema and image record model."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filepath TEXT NOT NULL UNIQUE,
    filename TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    file_mtime REAL NOT NULL,
    caption TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '[]',
    ocr_text TEXT NOT NULL DEFAULT '',
    embedding BLOB,
    indexed_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_images_hash ON images(file_hash);
CREATE INDEX IF NOT EXISTS idx_images_filename ON images(filename);
"""


@dataclass
class ImageRecord:
    id: int | None
    filepath: str
    filename: str
    file_hash: str
    file_size: int
    file_mtime: float
    caption: str
    tags: list[str]
    ocr_text: str
    embedding: list[float] | None
    indexed_at: str
    updated_at: str

    @property
    def searchable_text(self) -> str:
        tags_str = ", ".join(self.tags)
        parts = [self.caption, tags_str, self.ocr_text, self.filename]
        return " | ".join(p for p in parts if p)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "filepath": self.filepath,
            "filename": self.filename,
            "file_hash": self.file_hash,
            "file_size": self.file_size,
            "file_mtime": self.file_mtime,
            "caption": self.caption,
            "tags": self.tags,
            "ocr_text": self.ocr_text,
            "indexed_at": self.indexed_at,
            "updated_at": self.updated_at,
        }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(CREATE_TABLES_SQL)
    row = conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
    if row is None:
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
    conn.commit()


def row_to_record(row: sqlite3.Row) -> ImageRecord:
    tags = json.loads(row["tags"]) if row["tags"] else []
    embedding = None
    if row["embedding"]:
        import numpy as np

        embedding = np.frombuffer(row["embedding"], dtype=np.float32).tolist()

    return ImageRecord(
        id=row["id"],
        filepath=row["filepath"],
        filename=row["filename"],
        file_hash=row["file_hash"],
        file_size=row["file_size"],
        file_mtime=row["file_mtime"],
        caption=row["caption"],
        tags=tags,
        ocr_text=row["ocr_text"],
        embedding=embedding,
        indexed_at=row["indexed_at"],
        updated_at=row["updated_at"],
    )
