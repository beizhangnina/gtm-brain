"""gtm-brain CLI。

设计原则：每个命令都幂等，跑第二遍应该几乎零动作。
中断随时重跑，不需要 --resume 这种开关。
"""

from __future__ import annotations

import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import typer
from rich.console import Console
from rich.progress import (
    BarColumn, MofNCompleteColumn, Progress, SpinnerColumn,
    TextColumn, TimeElapsedColumn, TimeRemainingColumn,
)
from rich.table import Table

from . import images as imagelib
from . import brain as brainlib
from . import notes as noteslib
from . import pipeline, storage as storagelib, vault
from .config import REPO_ROOT, Config
from . import state as statelib
from .state import State

app = typer.Typer(
    add_completion=False,
    help="把 Obsidian GTM vault 对账进带图的托管 gbrain MCP",
    no_args_is_help=True,
)
console = Console()


def _mb(n: float) -> str:
    return f"{n / 1024 / 1024:,.1f} MB"


@app.command()
def status() -> None:
    """扫一眼 vault 现状和对账进度。"""
    cfg = Config.load()
    v = cfg.require_vault()

    counts = vault.count(v)
    t = Table(title="Vault（只读真源）", show_header=False, box=None)
    t.add_row("路径", str(v))
    t.add_row("笔记", f"{counts['notes']:,} 篇 / {counts['notes_mb']} MB")
    t.add_row("图片", f"{counts['images']:,} 张 / {counts['images_gb']} GB")
    console.print(t)

    st = State(cfg.state_db)
    s = st.image_stats()
    st.close()
    if not s["total"]:
        console.print("\n[dim]还没建过索引。跑 [bold]gtm-brain slim[/bold] 开始。[/dim]")
        return

    saved = s["src_bytes"] - s["out_bytes"]
    t2 = Table(title="\n图片处理进度", show_header=False, box=None)
    t2.add_row("已瘦身", f"{s['slimmed']:,} / {counts['images']:,}")
    t2.add_row("已上传", f"{s['uploaded']:,}")
    t2.add_row("失败", f"{s['failed']:,}")
    t2.add_row("去重后唯一衍生品", f"{s['unique_derivatives']:,}")
    if s["src_bytes"]:
        t2.add_row("体积", f"{_mb(s['src_bytes'])} → {_mb(s['out_bytes'])}"
                           f"  (省 {saved / s['src_bytes'] * 100:.0f}%)")
    console.print(t2)

    t3 = Table(title="\n配置", show_header=False, box=None)
    for label, value in [
        ("VOYAGE_API_KEY", cfg.voyage_api_key),
        ("SUPABASE_URL", cfg.supabase_url),
        ("SUPABASE_SERVICE_KEY", cfg.supabase_service_key),
        ("GTM_BRAIN_URL", cfg.brain_url),
    ]:
        t3.add_row(label, "[green]已配置[/green]" if value else "[yellow]待填[/yellow]")
    console.print(t3)


@app.command()
def slim(
    limit: int = typer.Option(0, help="只处理前 N 张，0 = 全部。用来小样试跑。"),
    workers: int = typer.Option(0, help="并行进程数，0 = CPU 核数 - 1"),
    force: bool = typer.Option(False, "--force", help="忽略缓存，全部重算"),
) -> None:
    """把 vault 图片压成 agent 友好的衍生品。只读 vault，绝不写入。"""
    cfg = Config.load()
    v = cfg.require_vault()
    st = State(cfg.state_db)

    all_assets = list(vault.iter_images(v))
    if force:
        todo = all_assets
    else:
        with console.status("检查哪些图变了…"):
            todo = [a for a in all_assets
                    if st.needs_slim(a.rel_path, vault.sha256_file(a.abs_path))]

    skipped = len(all_assets) - len(todo)
    if limit:
        todo = todo[:limit]

    console.print(f"图片总数 [bold]{len(all_assets):,}[/bold]   "
                  f"待处理 [bold]{len(todo):,}[/bold]   已是最新 [dim]{skipped:,}[/dim]")
    if not todo:
        console.print("[green]没有要做的。[/green]")
        st.close()
        return

    ok = failed = 0
    tot_in = tot_out = 0
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
        BarColumn(), MofNCompleteColumn(), TimeElapsedColumn(), TimeRemainingColumn(),
        console=console,
    ) as prog:
        task = prog.add_task("瘦身中", total=len(todo))
        for r in pipeline.slim_many(todo, REPO_ROOT, workers or None):
            if r.error:
                failed += 1
                st.record_image_error(r.rel_path, r.src_sha256, r.error)
            else:
                ok += 1
                tot_in += r.src_bytes
                tot_out += r.out_bytes
                st.record_slim(r.rel_path, r.src_sha256, r.src_bytes,
                               r.derivative_sha256, r.out_bytes)
            prog.advance(task)

    st.close()
    console.print(f"\n完成 [green]{ok:,}[/green]   失败 "
                  f"[{'red' if failed else 'dim'}]{failed:,}[/]")
    if tot_in:
        console.print(f"体积 {_mb(tot_in)} → {_mb(tot_out)}  "
                      f"(压缩 [bold]{tot_in / max(tot_out, 1):.1f}x[/bold])")
    if failed:
        console.print("[yellow]失败详情：state.db 的 images.error 字段[/yellow]")


@app.command()
def upload(
    limit: int = typer.Option(0, help="只传前 N 个，0 = 全部"),
    workers: int = typer.Option(8, help="并发上传数"),
) -> None:
    """把衍生品传到 Supabase Storage，内容寻址、幂等。"""
    import httpx
    from concurrent.futures import ThreadPoolExecutor, as_completed

    cfg = Config.load()
    st = State(cfg.state_db)
    store = storagelib.from_config(cfg)

    rows = st.conn.execute(
        "SELECT rel_path, derivative_sha256, out_bytes FROM images "
        "WHERE derivative_sha256 IS NOT NULL AND error IS NULL"
    ).fetchall()
    if not rows:
        console.print("[yellow]还没有衍生品。先跑 gtm-brain slim。[/yellow]")
        st.close()
        return

    done = st.uploaded_derivatives()
    # 内容寻址 → 同 hash 只需传一次，但每条 rel_path 都要记 URL
    by_sha: dict[str, list[str]] = {}
    for r in rows:
        by_sha.setdefault(r["derivative_sha256"], []).append(r["rel_path"])
    pending = {sha: paths for sha, paths in by_sha.items() if sha not in done}

    console.print(f"引用 [bold]{len(rows):,}[/bold] 条 → 去重后 [bold]{len(by_sha):,}[/bold] 个对象"
                  f"   待传 [bold]{len(pending):,}[/bold]   已传 [dim]{len(done):,}[/dim]")

    with httpx.Client(timeout=60) as client:
        console.print(f"bucket '{store.bucket}': {store.ensure_bucket(client)}")
        if not pending:
            # 即便没有新对象，也要把 URL 回填到还没记录的 rel_path 上
            _backfill_urls(st, store, by_sha, done)
            console.print("[green]没有要传的。[/green]")
            st.close()
            return

        items = list(pending.items())[:limit] if limit else list(pending.items())

        def _one(item):
            sha, paths = item
            cached = _find_cached(sha)
            if cached is None:
                return sha, paths, None, "本地缓存缺失，重跑 slim --force"
            key = imagelib.object_key(sha, cached.suffix.lstrip("."))
            ctype = imagelib.CONTENT_TYPES.get(cached.suffix.lower(), "application/octet-stream")
            try:
                url = store.upload(client, key, cached.read_bytes(), ctype)
                return sha, paths, url, None
            except Exception as exc:
                return sha, paths, None, repr(exc)[:200]

        ok = failed = 0
        with Progress(
            SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
            BarColumn(), MofNCompleteColumn(), TimeElapsedColumn(), TimeRemainingColumn(),
            console=console,
        ) as prog:
            task = prog.add_task("上传中", total=len(items))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                for fut in as_completed([pool.submit(_one, i) for i in items]):
                    sha, paths, url, err = fut.result()
                    if err:
                        failed += 1
                        console.print(f"[red]✗[/red] {sha[:12]} {err}")
                    else:
                        ok += 1
                        for p in paths:
                            st.record_upload(p, url)
                    prog.advance(task)

    st.close()
    console.print(f"\n上传成功 [green]{ok:,}[/green]   失败 [{'red' if failed else 'dim'}]{failed:,}[/]")
    if failed:
        raise typer.Exit(1)


def _find_cached(sha: str):
    d = REPO_ROOT / pipeline.CACHE_DIR_NAME / sha[:2]
    if not d.is_dir():
        return None
    for f in d.glob(f"{sha}.*"):
        if not f.name.endswith(".tmp"):
            return f
    return None


def _backfill_urls(st, store, by_sha, done) -> None:
    for sha, paths in by_sha.items():
        if sha not in done:
            continue
        cached = _find_cached(sha)
        if cached is None:
            continue
        url = store.public_url(imagelib.object_key(sha, cached.suffix.lstrip(".")))
        for p in paths:
            st.record_upload(p, url)


@app.command()
def ingest(
    limit: int = typer.Option(0, help="只处理前 N 篇，0 = 全部"),
    dry_run: bool = typer.Option(False, "--dry-run", help="只打印将写入什么，不碰 brain"),
    force: bool = typer.Option(False, "--force", help="忽略缓存，全部重推"),
    workers: int = typer.Option(4, help="并发写入数。服务端对同一 source 串行写入，\n开多了只会多抢锁（G-013）"),
) -> None:
    """把笔记推进 gbrain：相对路径 → 绝对 URL，打 tag，put_page。"""
    import httpx

    cfg = Config.load()
    v = cfg.require_vault()
    st = State(cfg.state_db)
    url_map = st.url_map()

    if not url_map and not dry_run:
        console.print("[yellow]还没有任何图片 URL。先跑 slim + upload，"
                      "否则推进去的正文里全是本地相对路径，agent 看不到图。[/yellow]")
        st.close()
        return

    # 要不要推，看的是「推上去的内容」有没有变，不只是笔记源文件（G-014）：
    # 笔记没改、但它引用的图后来才上传，渲染出来的正文也变了，同样要重推。
    # 全量渲染一遍只要一两秒，比漏推便宜得多。
    todo = []
    total = 0
    for a in vault.iter_notes(v):
        total += 1
        data = a.abs_path.read_bytes()
        n = noteslib.parse(a.rel_path, data.decode("utf-8", errors="replace"))
        r = noteslib.rewrite_images(n.body, a.rel_path, url_map)
        md = noteslib.to_markdown(n, r.body)
        pushed = hashlib.sha256(md.encode("utf-8")).hexdigest()
        row = st.conn.execute(
            "SELECT pushed_sha256 FROM notes WHERE rel_path = ?", (a.rel_path,)
        ).fetchone()
        if force or row is None or row["pushed_sha256"] != pushed:
            todo.append((a, hashlib.sha256(data).hexdigest(), n, r, md, pushed))

    console.print(f"笔记 [bold]{total:,}[/bold] 篇   "
                  f"待处理 [bold]{len(todo):,}[/bold]   图片 URL [dim]{len(url_map):,}[/dim]")
    if limit:
        todo = todo[:limit]
    if not todo:
        console.print("[green]都是最新的。[/green]")
        st.close()
        return

    if dry_run:
        for _, _, n, r, _, _ in todo[:5]:
            console.print(f"\n[bold]{n.slug}[/bold]")
            console.print(f"  title  {n.title[:70]}")
            console.print(f"  date   {n.date}   tags {n.tags}")
            console.print(f"  图片   重写 {r.rewritten}  死链 {len(r.unresolved)}  正文 {len(r.body):,} 字符")
        console.print(f"\n[dim]（--dry-run，只显示前 5 篇，共 {len(todo):,} 篇待处理）[/dim]")
        st.close()
        return

    bc = brainlib.from_config(cfg)
    ok = failed = 0
    dead_total = 0
    lock = threading.Lock()

    def _one(item):
        _, _, n, _, md, _ = item
        # 每个线程一个 client：httpx.Client 不保证跨线程共享安全
        with httpx.Client(timeout=300) as client:
            brainlib.put_page_sync(bc, client, n.slug, md)

    def _record_ok(item, pushed: str | None):
        """pushed=None：没能确认是这一版落的库，留空让下次重推（幂等，只是多一次写）。"""
        a, src, n, _, _, _ = item
        with st.tx() as c:
            c.execute(
                """INSERT INTO notes (rel_path, src_sha256, seen_at, slug,
                                      ingested_sha256, pushed_sha256, ingested_at, error)
                   VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                   ON CONFLICT(rel_path) DO UPDATE SET
                     src_sha256=excluded.src_sha256, slug=excluded.slug,
                     ingested_sha256=excluded.ingested_sha256,
                     pushed_sha256=excluded.pushed_sha256,
                     ingested_at=excluded.ingested_at, error=NULL""",
                (a.rel_path, src, statelib.now(), n.slug, src, pushed, statelib.now()),
            )

    with httpx.Client(timeout=120) as boot:
        # 预取 token，避免 N 个线程同时去换。
        # 必须带重试 —— 这里一次 ReadTimeout 曾让跑了 11 小时的任务
        # 在重启的启动阶段直接崩掉（G-012）。
        brainlib.with_network_retry(lambda: bc.token(boot), what="取 token")
        brainlib.with_network_retry(lambda: bc.initialize(boot), what="MCP initialize")

    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
        BarColumn(), MofNCompleteColumn(), TimeElapsedColumn(), TimeRemainingColumn(),
        console=console,
    ) as prog:
        task = prog.add_task("ingest", total=len(todo))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_one, it): it for it in todo}
            for fut in as_completed(futures):
                item = futures[fut]
                a, src, n, r, _, pushed = item
                try:
                    fut.result()
                    with lock:
                        ok += 1
                        dead_total += len(r.unresolved)
                        _record_ok(item, pushed)
                except Exception as exc:
                    # 写入是 durable 的：超时不代表没落库。
                    # 标失败前先回读，避免把成功算成失败。
                    # 但回读只能证明页面存在，不能证明是这一版 —— 所以不记 pushed_sha256。
                    landed = False
                    try:
                        with httpx.Client(timeout=60) as vc:
                            chk = brainlib.with_network_retry(
                                lambda: bc.call(vc, "get_page", {"slug": n.slug}),
                                attempts=3, what="回读确认")
                            landed = brainlib.mcp_error(chk) is None
                    except Exception:
                        pass
                    with lock:
                        if landed:
                            ok += 1
                            _record_ok(item, None)
                        else:
                            failed += 1
                            with st.tx() as c:
                                c.execute(
                                    """INSERT INTO notes (rel_path, src_sha256, seen_at, error)
                                       VALUES (?, ?, ?, ?)
                                       ON CONFLICT(rel_path) DO UPDATE SET error=excluded.error""",
                                    (a.rel_path, src, statelib.now(), repr(exc)[:400]),
                                )
                prog.advance(task)

    st.close()
    console.print(f"\ningest 成功 [green]{ok:,}[/green]   失败 "
                  f"[{'red' if failed else 'dim'}]{failed:,}[/]   "
                  f"保留的死图链 [dim]{dead_total}[/dim]")
    if failed:
        raise typer.Exit(1)


@app.command()
def failures(limit: int = 20) -> None:
    """列出瘦身失败的图，方便排查。"""
    cfg = Config.load()
    st = State(cfg.state_db)
    rows = st.conn.execute(
        "SELECT rel_path, error FROM images WHERE error IS NOT NULL LIMIT ?", (limit,)
    ).fetchall()
    st.close()
    if not rows:
        console.print("[green]没有失败记录。[/green]")
        return
    for r in rows:
        console.print(f"[red]✗[/red] {r['rel_path']}\n  {r['error']}")


if __name__ == "__main__":
    app()
