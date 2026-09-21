"""笔记解析 + 图片链接重写。

核心转换：vault 里的相对路径（Obsidian 要的） → 云端绝对 URL（agent 要的）。
同一份 markdown，两种读者，只在 ingest 那一刻做一次字符串替换。
vault 文件本身永不改动。
"""

from __future__ import annotations

import hashlib
import posixpath
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from urllib.parse import unquote

import frontmatter

# 实测全库 7,093 个图片引用：./ 开头 6,739、裸相对 337、../ 13、远端 http 4。
# 路径里零空格，但 524 个带 `"title"` 后缀 —— 不处理的话会把 title 当成路径的一部分。
IMAGE_RE = re.compile(
    r"""!\[(?P<alt>[^\]]*)\]\(\s*(?P<path><[^>]+>|[^)\s]+)(?P<title>\s+"[^"]*")?\s*\)""",
)

SERIES: dict[str, tuple[str, str]] = {
    # vault 文件夹名 → (slug 前缀, series tag)
    "Lenny's Newsletter": ("lennys-", "lennys-newsletter"),
    "Growth Unhinged": ("growth-unhinged-", "growth-unhinged"),
    "Marketing Ideas": ("marketing-ideas-", "marketing-ideas"),
    "Fletch PMM": ("fletch-pmm-", "fletch-pmm"),
    "MRR Unlocked": ("mrr-unlocked-", "mrr-unlocked"),
}

DATE_PREFIX_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\s+(.*)$")
SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")


@dataclass
class RewriteResult:
    body: str
    rewritten: int = 0
    remote_skipped: int = 0
    unresolved: list[str] = field(default_factory=list)


def rewrite_images(body: str, note_rel_path: str, url_map: dict[str, str]) -> RewriteResult:
    """把正文里的本地图片链接换成绝对 URL。

    `url_map` 的键是 vault 相对路径（POSIX）。解析不到的链接**原样保留** ——
    宁可留一个坏链，也不要悄悄吞掉内容。
    """
    note_dir = PurePosixPath(note_rel_path).parent
    res = RewriteResult(body="")
    unresolved: list[str] = []
    rewritten = remote = 0

    def _sub(m: re.Match[str]) -> str:
        nonlocal rewritten, remote
        raw = m.group("path").strip()
        if raw.startswith("<") and raw.endswith(">"):
            raw = raw[1:-1]
        if raw.startswith(("http://", "https://", "data:")):
            remote += 1
            return m.group(0)

        # Obsidian 写的是 URL 形式，%20 之类要先还原成真实文件名
        candidate = posixpath.normpath(posixpath.join(str(note_dir), unquote(raw)))
        url = url_map.get(candidate)
        if url is None:
            unresolved.append(candidate)
            return m.group(0)

        rewritten += 1
        title = m.group("title") or ""
        return f"![{m.group('alt')}]({url}{title})"

    res.body = IMAGE_RE.sub(_sub, body)
    res.rewritten = rewritten
    res.remote_skipped = remote
    res.unresolved = unresolved
    return res


def _slugify(text: str) -> str:
    return SLUG_STRIP_RE.sub("-", text.lower()).strip("-")[:90]


def _short_hash(text: str, n: int = 6) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:n]


def _lossy(original: str, slugified: str) -> bool:
    """slugify 是否丢掉了大部分信息（典型情况：纯中文标题被剥光）。"""
    meaningful = len(slugified.replace("-", ""))
    return meaningful < max(4, len(original.strip()) * 0.3)


@dataclass
class ParsedNote:
    rel_path: str
    slug: str
    title: str
    body: str
    metadata: dict
    tags: list[str]
    series: str | None
    date: str | None


def parse(rel_path: str, raw: str) -> ParsedNote:
    """解析一篇笔记，产出 gbrain put_page 需要的字段。

    Tag 规则（全新 brain，五个系列统一，不为任何一个破例）：
      series:<slug> / source:newsletter|playbook / year:<YYYY> / gtm
    Fletch PMM 额外带 industry:<lowercase>。
    """
    post = frontmatter.loads(raw)
    meta = dict(post.metadata)
    parts = PurePosixPath(rel_path).parts
    stem = PurePosixPath(rel_path).stem

    series_folder = parts[1] if len(parts) > 2 and parts[0] == "Newsletters" else None
    prefix, series_tag = SERIES.get(series_folder or "", ("", ""))

    # 日期来源：文件名前缀优先，其次 frontmatter.date，最后 frontmatter.scraped
    # （Fletch PMM 按公司名命名，没有日期前缀，只有 scraped）
    date = None
    name_body = stem
    if m := DATE_PREFIX_RE.match(stem):
        date, name_body = m.group(1), m.group(2)
    for key in ("date", "scraped", "published"):
        if date:
            break
        if value := meta.get(key):
            date = str(value)[:10]

    # slug 必须在全库唯一 —— gbrain 的 put_page 按 slug upsert，
    # 撞车 = 静默覆盖。实测过的真实坑：Lenny's 有 9 篇都叫
    # "Taking the week off"（不同年份的休刊通知），不带日期会塌缩成 1 篇。
    if series_folder:
        body_slug = _slugify(name_body)
        # 有日期就带上 —— 日期是天然的消歧符，也让 slug 可排序
        slug = f"{prefix}{date}-{body_slug}" if date else f"{prefix}{body_slug}"
        if _lossy(name_body, body_slug):
            slug = f"{slug}-{_short_hash(rel_path)}"
        source_tag = "source:newsletter"
    else:
        body_slug = _slugify(stem)
        slug = f"playbook-{body_slug}"
        # 中文标题被 slugify 剥光后极易撞车（GEO白皮书 / GEO红皮书 都变成 geo-）
        if _lossy(stem, body_slug):
            slug = f"{slug}-{_short_hash(rel_path)}"
        source_tag = "source:playbook"

    tags = ["gtm", source_tag]
    if series_tag:
        tags.append(f"series:{series_tag}")
    if date and len(date) >= 4 and date[:4].isdigit():
        tags.append(f"year:{date[:4]}")
    for industry in meta.get("industry", []) or []:
        tags.append(f"industry:{_slugify(str(industry))}")

    return ParsedNote(
        rel_path=rel_path,
        slug=slug,
        title=str(meta.get("title") or name_body),
        body=post.content,
        metadata=meta,
        tags=sorted(set(tags)),
        series=series_folder,
        date=date,
    )


def to_markdown(note: ParsedNote, body: str) -> str:
    """组装成 gbrain put_page 要的完整 markdown（YAML frontmatter + 正文）。

    put_page 的 `content` 是**整页替换**，frontmatter 也在里面 ——
    tags 没有独立参数，必须写进 frontmatter。
    """
    import yaml

    fm: dict = {"title": note.title, "tags": note.tags}
    if note.date:
        fm["date"] = note.date
    for k in ("source", "subtitle", "author", "industry", "upstream_url", "license"):
        if (v := note.metadata.get(k)) not in (None, ""):
            fm[k] = v
    head = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, default_flow_style=False)
    return f"---\n{head}---\n\n{body}"
