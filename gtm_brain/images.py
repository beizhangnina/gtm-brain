"""图片瘦身：vault 原图 → 给 agent 看的 WebP 衍生品。

为什么要瘦身，不是为了省钱（R2/Supabase 都装得下），是为了**可用性**：
vault 里最大的图是 20MB 的 GIF，agent fetch 一张要等很久。衍生品
把它压到 ~100KB，同时内容完全看得清。

不变式：只读源文件，产出在内存里，vault 一个字节不动。
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageSequence

# newsletter 截图不会是解压炸弹，但也别完全关掉保护
Image.MAX_IMAGE_PIXELS = 300_000_000

# 按【宽度】限制，不是最长边。
# 教训：库里 5% 是整页网站截图（Fletch PMM 的 Before/After 最典型，
# 实测 800x4205 ~ 1889x8391）。按最长边缩会把 1889x8391 压成 152x1600 ——
# 宽度只剩 152px，文字全糊，而那恰恰是这个系列最有价值的内容。
# 宽度决定文字可读性，高度不决定。实测全库宽度 p50=1456 / p90=1456 / max=2820，
# 所以 1600 这个阈值对绝大多数图根本不触发。
DEFAULT_MAX_WIDTH = 1600

# WebP 单边硬上限是 16383，留出余量
DEFAULT_MAX_HEIGHT = 12000

DEFAULT_QUALITY = 80

# Pillow 处理不了的，原样透传（SVG 是矢量文本，本来就小）
PASSTHROUGH_SUFFIXES = {".svg"}

# 已经是网页原生格式的，若转 WebP 不省体积就别转
WEB_NATIVE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}

# 但再怎么「已经够小」也有上限 —— 超过这个一律重编码
PASSTHROUGH_SIZE_CEILING = 400 * 1024

CONTENT_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".bmp": "image/bmp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}


@dataclass(frozen=True)
class Derivative:
    data: bytes
    ext: str            # 不带点，例 "webp"
    content_type: str
    width: int | None
    height: int | None
    was_animated: bool
    passthrough: bool   # True = 原样透传，没重编码
    reason: str = ""    # 透传的原因，便于统计


def _flatten_to_supported_mode(im: Image.Image) -> Image.Image:
    """WebP 只认 RGB / RGBA。其余模式安全转换，保住透明通道。"""
    if im.mode in ("RGB", "RGBA"):
        return im
    if im.mode in ("LA", "PA"):
        return im.convert("RGBA")
    if im.mode == "P":
        # 调色板图可能带透明色索引
        return im.convert("RGBA" if "transparency" in im.info else "RGB")
    if im.mode in ("1", "L", "I", "F", "I;16"):
        return im.convert("RGB")
    if im.mode == "CMYK":
        return im.convert("RGB")
    return im.convert("RGB")


def _target_size(
    w: int, h: int, max_width: int, max_height: int
) -> tuple[int, int] | None:
    """只在超限时等比缩小。返回 None 表示原尺寸就行，别动它。"""
    scale = 1.0
    if w > max_width:
        scale = max_width / w
    if h * scale > max_height:
        scale = max_height / h
    if scale >= 1.0:
        return None
    return max(1, round(w * scale)), max(1, round(h * scale))


def slim(
    src: Path,
    max_width: int = DEFAULT_MAX_WIDTH,
    max_height: int = DEFAULT_MAX_HEIGHT,
    quality: int = DEFAULT_QUALITY,
) -> Derivative:
    """把一张图压成 agent 友好的 WebP。动图只取第一帧。"""
    suffix = src.suffix.lower()
    if suffix in PASSTHROUGH_SUFFIXES:
        return Derivative(
            data=src.read_bytes(),
            ext=suffix.lstrip("."),
            content_type="image/svg+xml",
            width=None,
            height=None,
            was_animated=False,
            passthrough=True,
            reason="vector",
        )

    with Image.open(src) as im:
        was_animated = bool(getattr(im, "is_animated", False))
        if was_animated:
            # 取首帧。agent 需要看清内容，不需要动画；
            # 一个 20MB 的 GIF 首帧通常就是它想表达的那一屏。
            frame = next(iter(ImageSequence.Iterator(im)))
            work = frame.copy()
            # 动 GIF 的帧常是局部调色板，先并回完整模式再缩放
            if work.mode == "P":
                work = work.convert("RGBA" if "transparency" in im.info else "RGB")
        else:
            work = im.copy()

        work = _flatten_to_supported_mode(work)

        target = _target_size(work.width, work.height, max_width, max_height)
        if target:
            work = work.resize(target, Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        work.save(buf, format="WEBP", quality=quality, method=6)
        data = buf.getvalue()

    # 「不许变大」保护：本来就小又已经是网页友好格式的图，
    # 转 WebP 常常一点不省甚至更大（实测 84KB PNG → 84.1KB WebP）。
    # 那就别折腾，原样透传 —— 少一次重编码就少一次画质损失。
    src_size = src.stat().st_size
    if (
        not was_animated
        and len(data) >= src_size * 0.95
        and suffix in WEB_NATIVE_SUFFIXES
        and src_size <= PASSTHROUGH_SIZE_CEILING
    ):
        return Derivative(
            data=src.read_bytes(),
            ext=suffix.lstrip(".").replace("jpeg", "jpg"),
            content_type=CONTENT_TYPES[suffix],
            width=work.width,
            height=work.height,
            was_animated=False,
            passthrough=True,
            reason="webp-not-smaller",
        )

    return Derivative(
        data=data,
        ext="webp",
        content_type="image/webp",
        width=work.width,
        height=work.height,
        was_animated=was_animated,
        passthrough=False,
    )


def object_key(derivative_sha256: str, ext: str) -> str:
    """内容寻址路径：不可枚举、天然去重、可设 immutable 缓存。"""
    return f"{derivative_sha256[:2]}/{derivative_sha256}.{ext}"
