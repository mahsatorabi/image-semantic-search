"""Orchestrates scanning, AI analysis, and database storage."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ai_image_indexer.cloudflare.client import CloudflareAIClient
from ai_image_indexer.config import Settings
from ai_image_indexer.database.repository import ImageRepository
from ai_image_indexer.database.schema import ImageRecord, utc_now_iso
from ai_image_indexer.scanner.scanner import ScannedImage, needs_reindex, scan_folder


@dataclass
class IndexStats:
    scanned: int = 0
    indexed: int = 0
    skipped: int = 0
    failed: int = 0
    removed: int = 0


ProgressCallback = Callable[[str, int, int], None]


def _is_under(path: str, root: str) -> bool:
    try:
        return Path(path).resolve().is_relative_to(Path(root).resolve())
    except (OSError, ValueError):
        return path.startswith(root.rstrip("\\/") + "/") or path.startswith(
            root.rstrip("\\/") + "\\"
        )


class IndexingPipeline:
    def __init__(
        self,
        settings: Settings,
        repo: ImageRepository,
        ai_client: CloudflareAIClient,
    ) -> None:
        self.settings = settings
        self.repo = repo
        self.ai_client = ai_client

    def run(
        self,
        folders: Path | list[Path],
        *,
        force: bool = False,
        on_progress: ProgressCallback | None = None,
    ) -> IndexStats:
        if isinstance(folders, Path):
            folder_list = [folders]
        else:
            folder_list = list(folders)

        stats = IndexStats()
        images_by_path: dict[str, ScannedImage] = {}

        for folder in folder_list:
            for img in scan_folder(folder):
                images_by_path[str(img.filepath)] = img

        images = list(images_by_path.values())
        stats.scanned = len(images)

        valid_paths: set[str] = set()
        to_process: list[ScannedImage] = []

        for img in images:
            path_str = str(img.filepath)
            valid_paths.add(path_str)
            existing = self.repo.get_by_filepath(path_str)

            if force or needs_reindex(
                img,
                existing.file_hash if existing else None,
                existing.file_mtime if existing else None,
                existing.file_size if existing else None,
            ):
                to_process.append(img)
            else:
                stats.skipped += 1

        total = len(to_process)
        for i, img in enumerate(to_process, start=1):
            if on_progress:
                on_progress(img.filename, i, total)
            try:
                self._index_one(img)
                stats.indexed += 1
            except Exception:
                stats.failed += 1

        for folder in folder_list:
            root = str(folder.resolve())
            folder_paths = {path for path in valid_paths if _is_under(path, root)}
            stats.removed += self.repo.remove_stale_under_prefix(root, folder_paths)

        return stats

    def _index_one(self, scanned: ScannedImage) -> ImageRecord:
        analysis = self.ai_client.analyze_image(scanned.filepath)
        searchable = " | ".join(
            filter(
                None,
                [
                    analysis["caption"],
                    ", ".join(analysis["tags"]),
                    analysis["ocr_text"],
                    scanned.filename,
                ],
            )
        )
        embedding = self.ai_client.embed_text(searchable)
        now = utc_now_iso()

        record = ImageRecord(
            id=None,
            filepath=str(scanned.filepath),
            filename=scanned.filename,
            file_hash=scanned.file_hash,
            file_size=scanned.file_size,
            file_mtime=scanned.file_mtime,
            caption=str(analysis["caption"]),
            tags=list(analysis["tags"]),
            ocr_text=str(analysis["ocr_text"]),
            embedding=embedding,
            indexed_at=now,
            updated_at=now,
        )
        return self.repo.upsert(record)
