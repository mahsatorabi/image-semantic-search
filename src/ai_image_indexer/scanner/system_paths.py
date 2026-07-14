"""Default image folder locations per operating system."""

from __future__ import annotations

import os
import platform
from pathlib import Path


def _existing(path: Path) -> Path | None:
    try:
        resolved = path.expanduser().resolve()
    except OSError:
        return None
    if resolved.is_dir():
        return resolved
    return None


def default_system_image_roots() -> list[Path]:
    """Return common user image folders for the current OS."""
    home = Path.home()
    candidates: list[Path] = []

    system = platform.system()
    if system == "Windows":
        candidates.extend(
            [
                home / "Pictures",
                home / "Downloads",
                home / "Desktop",
                home / "OneDrive" / "Pictures",
                home / "OneDrive" / "Desktop",
                home / "OneDrive" / "Downloads",
                Path(os.environ.get("USERPROFILE", str(home))) / "Pictures",
            ]
        )
        public_pictures = Path(os.environ.get("PUBLIC", "")) / "Pictures"
        if public_pictures.parts[0]:
            candidates.append(public_pictures)
    elif system == "Darwin":
        candidates.extend(
            [
                home / "Pictures",
                home / "Downloads",
                home / "Desktop",
                home / "Library" / "Mobile Documents" / "com~apple~CloudDocs",
            ]
        )
    else:
        candidates.extend(
            [
                home / "Pictures",
                home / "Downloads",
                home / "Desktop",
                home / "Documents",
            ]
        )
        xdg_pictures = os.environ.get("XDG_PICTURES_DIR")
        if xdg_pictures:
            candidates.append(Path(xdg_pictures))

    seen: set[Path] = set()
    roots: list[Path] = []
    for candidate in candidates:
        existing = _existing(candidate)
        if existing is None or existing in seen:
            continue
        seen.add(existing)
        roots.append(existing)

    return roots


def resolve_scan_roots(extra_paths: list[Path] | None = None) -> list[Path]:
    """Merge configured paths with OS defaults, deduplicated and validated."""
    roots: list[Path] = []
    seen: set[Path] = set()

    for path in extra_paths or []:
        existing = _existing(path)
        if existing is None or existing in seen:
            continue
        seen.add(existing)
        roots.append(existing)

    if not roots:
        for path in default_system_image_roots():
            if path not in seen:
                seen.add(path)
                roots.append(path)

    return roots
