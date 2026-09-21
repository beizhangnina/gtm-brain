# gtm-brain

把 Obsidian 里的 GTM 知识库（1,200+ 篇 newsletter + 7,000+ 张配图）对账进一个
**带图的托管 MCP**，让自己和少数同事在 Claude Code / Codex 里都能检索到正文
**并看到图**。

## 它是什么，不是什么

**是**一个 vault 对账器。它只读 Obsidian vault，不关心内容是谁写进去的
（目前是 Grok Bot 在持续更新）。抓取层换成别的，这里一行都不用改。

**不是**爬虫。没有 RSS、没有 IMAP、没有浏览器自动化。

## 核心设计

```
Obsidian vault（只读真源，永不写入）
        ↓
  1. 按 sha256 找出变化的 .md
  2. 图片瘦身 → WebP 衍生品
  3. 内容寻址上传 → Supabase Storage
  4. 正文 ./images/... → 绝对 URL
  5. put_page → gbrain
        ↓
  Railway 上的 gbrain HTTP MCP (OAuth)
```

**不变式：vault 存原图（Obsidian 体验），云端存瘦身衍生品（agent 体验）。**
同一份 markdown，两种读者，只在 ingest 那一刻做一次字符串替换，vault 文件本身
永不改动。

每一步都幂等 —— 跑第二遍几乎零动作，中断随时重跑，不需要 `--resume`。

## 为什么要瘦身

不是为了省钱（存储额度绰绰有余），是为了**可用性**：vault 里最大的图是 36 MB
的 GIF，agent fetch 一张要等很久。衍生品把它压到 ~100KB，内容完全看得清。

实测：**2.5 GB → 约 0.5 GB**，动图能压 200–1000x。

⚠️ 缩放按**宽度**限制，不是最长边 —— 详见 [docs/gotchas.md](docs/gotchas.md) G-001，
那个坑会安静地毁掉整页截图（库里最有价值的 Before/After 对比图）。

## 用法

```bash
cp .env.example .env    # 填 key
uv sync

uv run gtm-brain status           # 看 vault 现状和对账进度
uv run gtm-brain slim             # 图片瘦身（并行，只读 vault）
uv run gtm-brain slim --limit 50  # 小样试跑
uv run gtm-brain upload           # 传到 Supabase Storage
uv run gtm-brain failures         # 看失败详情
```

`state.db` 和 `.cache/` 都是可重建的缓存，删掉重跑即可，里面没有真源。

## 文档

- [docs/gotchas.md](docs/gotchas.md) — 踩过的坑
- [tasks/todo.md](tasks/todo.md) — 实施进度
- [tasks/lessons.md](tasks/lessons.md) — 经验教训
