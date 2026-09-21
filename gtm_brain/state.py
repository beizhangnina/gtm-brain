"""SQLite 状态库。可随时删掉重建 —— 里面没有真源，只有加速用的缓存。"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    rel_path         TEXT PRIMARY KEY,
    src_sha256       TEXT NOT NULL,
    seen_at          TEXT NOT NULL,
    slug             TEXT,
    ingested_sha256  TEXT,
    ingested_at      TEXT,
    error            TEXT
);

CREATE TABLE IF NOT EXISTS images (
    rel_path          TEXT PRIMARY KEY,
    src_sha256        TEXT NOT NULL,
    src_bytes         INTEGER,
    derivative_sha256 TEXT,
    out_bytes         INTEGER,
    slimmed_at        TEXT,
    uploaded_at       TEXT,
    public_url        TEXT,
    error             TEXT
);

CREATE INDEX IF NOT EXISTS idx_images_derivative ON images(derivative_sha256);
CREATE INDEX IF NOT EXISTS idx_images_uploaded   ON images(uploaded_at);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class State:
    def __init__(self, path: Path):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    # ---- images -------------------------------------------------

    def image_row(self, rel_path: str) -> sqlite3.Row | None:
        cur = self.conn.execute("SELECT * FROM images WHERE rel_path = ?", (rel_path,))
        return cur.fetchone()

    def needs_slim(self, rel_path: str, src_sha256: str) -> bool:
        """源没变且已成功产出衍生品 → 跳过。"""
        row = self.image_row(rel_path)
        if row is None:
            return True
        return not (row["src_sha256"] == src_sha256 and row["derivative_sha256"])

    def record_slim(
        self,
        rel_path: str,
        src_sha256: str,
        src_bytes: int,
        derivative_sha256: str,
        out_bytes: int,
    ) -> None:
        with self.tx() as c:
            c.execute(
                """
                INSERT INTO images
                    (rel_path, src_sha256, src_bytes, derivative_sha256, out_bytes, slimmed_at, error)
                VALUES (?, ?, ?, ?, ?, ?, NULL)
                ON CONFLICT(rel_path) DO UPDATE SET
                    src_sha256        = excluded.src_sha256,
                    src_bytes         = excluded.src_bytes,
                    derivative_sha256 = excluded.derivative_sha256,
                    out_bytes         = excluded.out_bytes,
                    slimmed_at        = excluded.slimmed_at,
                    error             = NULL,
                    -- 源变了就作废上传记录，强制重传
                    uploaded_at = CASE WHEN images.src_sha256 = excluded.src_sha256
                                       THEN images.uploaded_at ELSE NULL END,
                    public_url  = CASE WHEN images.src_sha256 = excluded.src_sha256
                                       THEN images.public_url ELSE NULL END
                """,
                (rel_path, src_sha256, src_bytes, derivative_sha256, out_bytes, now()),
            )

    def record_image_error(self, rel_path: str, src_sha256: str, message: str) -> None:
        with self.tx() as c:
            c.execute(
                """
                INSERT INTO images (rel_path, src_sha256, slimmed_at, error)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(rel_path) DO UPDATE SET
                    src_sha256 = excluded.src_sha256,
                    slimmed_at = excluded.slimmed_at,
                    error      = excluded.error
                """,
                (rel_path, src_sha256, now(), message[:500]),
            )

    def record_upload(self, rel_path: str, public_url: str) -> None:
        with self.tx() as c:
            c.execute(
                "UPDATE images SET uploaded_at = ?, public_url = ? WHERE rel_path = ?",
                (now(), public_url, rel_path),
            )

    def uploaded_derivatives(self) -> set[str]:
        """已经传上去的衍生品 hash 集合 —— 内容寻址下同 hash 不必重传。"""
        cur = self.conn.execute(
            "SELECT DISTINCT derivative_sha256 FROM images "
            "WHERE uploaded_at IS NOT NULL AND derivative_sha256 IS NOT NULL"
        )
        return {r[0] for r in cur}

    def url_map(self) -> dict[str, str]:
        """vault 相对路径 → 公网 URL。ingest 时用它重写正文链接。"""
        cur = self.conn.execute(
            "SELECT rel_path, public_url FROM images WHERE public_url IS NOT NULL"
        )
        return {r["rel_path"]: r["public_url"] for r in cur}

    def image_stats(self) -> dict[str, int]:
        cur = self.conn.execute(
            """
            SELECT
                COUNT(*)                                             AS total,
                SUM(derivative_sha256 IS NOT NULL)                   AS slimmed,
                SUM(uploaded_at IS NOT NULL)                         AS uploaded,
                SUM(error IS NOT NULL)                               AS failed,
                COALESCE(SUM(src_bytes), 0)                          AS src_bytes,
                COALESCE(SUM(out_bytes), 0)                          AS out_bytes,
                COUNT(DISTINCT derivative_sha256)                    AS unique_derivatives
            FROM images
            """
        )
        return dict(cur.fetchone())
