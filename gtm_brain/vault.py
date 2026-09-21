"""只读地扫描 Obsidian vault。本模块永不写入 vault。"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".tif", ".tiff"}
SKIP_DIRS = {".obsidian", ".trash", ".git", "node_modules", "__pycache__"}


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _walk(root: Path) -> Iterator[Path]:
    for p in root.rglob("*"):
        if p.is_dir():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.name.startswith("."):
            continue
        yield p


@dataclass(frozen=True)
class Asset:
    rel_path: str      # 相对 vault 根，POSIX 风格，作为稳定主键
    abs_path: Path
    size: int


def iter_notes(vault: Path) -> Iterator[Asset]:
    for p in _walk(vault):
        if p.suffix.lower() == ".md":
            yield Asset(p.relative_to(vault).as_posix(), p, p.stat().st_size)


def iter_images(vault: Path) -> Iterator[Asset]:
    for p in _walk(vault):
        if p.suffix.lower() in IMAGE_SUFFIXES:
            yield Asset(p.relative_to(vault).as_posix(), p, p.stat().st_size)


def count(vault: Path) -> dict[str, int | float]:
    notes = list(iter_notes(vault))
    images = list(iter_images(vault))
    return {
        "notes": len(notes),
        "notes_mb": round(sum(a.size for a in notes) / 1024 / 1024, 1),
        "images": len(images),
        "images_gb": round(sum(a.size for a in images) / 1024 / 1024 / 1024, 2),
    }
