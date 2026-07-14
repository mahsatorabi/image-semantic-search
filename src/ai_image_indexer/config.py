"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_VISION_MODEL = "@cf/unum/uform-gen2-qwen-500m"
DEFAULT_EMBEDDING_MODEL = "@cf/google/embeddinggemma-300m"
DEFAULT_DB_DIR = Path.home() / ".ai-image-indexer"
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "index.db"

IMAGE_EXTENSIONS = frozenset(
    {
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".bmp",
        ".webp",
        ".tiff",
        ".tif",
        ".heic",
        ".heif",
        ".avif",
        ".svg",
    }
)


def _parse_scan_paths(raw: str) -> tuple[Path, ...]:
    if not raw.strip():
        return ()
    paths: list[Path] = []
    for part in raw.split(","):
        part = part.strip()
        if part:
            paths.append(Path(part).expanduser())
    return tuple(paths)


@dataclass(frozen=True)
class Settings:
    account_id: str
    api_token: str
    vision_model: str
    embedding_model: str
    db_path: Path
    scan_paths: tuple[Path, ...] = ()
    api_base_url: str = "https://api.cloudflare.com/client/v4"
    request_timeout: float = 120.0
    max_retries: int = 3

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> Settings:
        if env_file and env_file.exists():
            load_dotenv(env_file)
        else:
            load_dotenv()

        account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
        api_token = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()

        if not account_id or not api_token:
            raise ValueError(
                "Missing Cloudflare credentials. Set CLOUDFLARE_ACCOUNT_ID and "
                "CLOUDFLARE_API_TOKEN in your environment or .env file.\n"
                "Get them from: https://dash.cloudflare.com → Workers AI → Use REST API"
            )

        db_path_raw = os.getenv("AI_IMAGE_INDEXER_DB_PATH", str(DEFAULT_DB_PATH))
        db_path = Path(db_path_raw).expanduser().resolve()

        return cls(
            account_id=account_id,
            api_token=api_token,
            vision_model=os.getenv("AI_IMAGE_INDEXER_VISION_MODEL", DEFAULT_VISION_MODEL),
            embedding_model=os.getenv(
                "AI_IMAGE_INDEXER_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL
            ),
            db_path=db_path,
            scan_paths=_parse_scan_paths(os.getenv("AI_IMAGE_INDEXER_SCAN_PATHS", "")),
        )

    def ensure_db_dir(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
