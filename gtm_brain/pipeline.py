"""瘦身流水线：并行处理 + 衍生品本地缓存。

拆成 slim / upload 两步而不是一步到底，是为了各自幂等：
瘦身很贵（CPU），上传很贵（网络），任何一步挂了都不该让另一步重来。
"""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from . import images, vault

CACHE_DIR_NAME = ".cache/derivatives"


@dataclass
class SlimResult:
    rel_path: str
    src_sha256: str
    src_bytes: int
    derivative_sha256: str | None
    out_bytes: int
    ext: str
    content_type: str
    passthrough: bool
    error: str | None = None


def cache_path(repo_root: Path, derivative_sha256: str, ext: str) -> Path:
    return repo_root / CACHE_DIR_NAME / derivative_sha256[:2] / f"{derivative_sha256}.{ext}"


def _slim_one(args: tuple[str, str, str]) -> SlimResult:
    """子进程里跑。参数用纯字符串，避免 pickle 复杂对象。"""
    rel_path, abs_path, repo_root = args
    src = Path(abs_path)
    try:
        src_sha = vault.sha256_file(src)
        src_bytes = src.stat().st_size
    except OSError as exc:
        return SlimResult(rel_path, "", 0, None, 0, "", "", False, f"读取失败: {exc}")

    try:
        d = images.slim(src)
    except Exception as exc:  # 单张坏图不该让整轮停下
        return SlimResult(rel_path, src_sha, src_bytes, None, 0, "", "", False, repr(exc)[:300])

    out_sha = vault.sha256_bytes(d.data)
    dest = cache_path(Path(repo_root), out_sha, d.ext)
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        tmp.write_bytes(d.data)
        os.replace(tmp, dest)  # 原子落盘，中断不会留半个文件

    return SlimResult(
        rel_path, src_sha, src_bytes, out_sha, len(d.data),
        d.ext, d.content_type, d.passthrough,
    )


def slim_many(
    assets: list[vault.Asset],
    repo_root: Path,
    workers: int | None = None,
):
    """并行瘦身，边跑边 yield 结果，方便调用方写进度和状态。"""
    workers = workers or max(1, (os.cpu_count() or 4) - 1)
    payload = [(a.rel_path, str(a.abs_path), str(repo_root)) for a in assets]
    if not payload:
        return
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_slim_one, item): item[0] for item in payload}
        for fut in as_completed(futures):
            yield fut.result()
