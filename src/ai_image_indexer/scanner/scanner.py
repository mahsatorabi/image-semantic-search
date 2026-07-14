"""Recursive image folder scanner with change detection."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from ai_image_indexer.config import IMAGE_EXTENSIONS


@dataclass(frozen=True)
class ScannedImage:
    filepath: Path
    filename: str
    file_hash: str
    file_size: int
    file_mtime: float


def is_image_file(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTENSIONS


def compute_file_hash(path: Path, chunk_size: int = 65536) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def scan_folder(
    root: Path,
    *,
    follow_symlinks: bool = False,
) -> list[ScannedImage]:
    root = root.expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"Folder not found: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Not a directory: {root}")

    results: list[ScannedImage] = []
    walker = os.walk(root, followlinks=follow_symlinks)

    for dirpath, _dirnames, filenames in walker:
        for name in filenames:
            path = Path(dirpath) / name
            if not is_image_file(path):
                continue
            try:
                stat = path.stat()
            except OSError:
                continue

            try:
                file_hash = compute_file_hash(path)
            except OSError:
                continue

            results.append(
                ScannedImage(
                    filepath=path.resolve(),
                    filename=path.name,
                    file_hash=file_hash,
                    file_size=stat.st_size,
                    file_mtime=stat.st_mtime,
                )
            )

    return results


def needs_reindex(
    scanned: ScannedImage,
    stored_hash: str | None,
    stored_mtime: float | None,
    stored_size: int | None,
) -> bool:
    if stored_hash is None:
        return True
    if scanned.file_hash != stored_hash:
        return True
    if stored_mtime is not None and scanned.file_mtime != stored_mtime:
        return True
    if stored_size is not None and scanned.file_size != stored_size:
        return True
    return False
