# GTM Brain

一个装着 **1,200+ 篇 GTM newsletter 和 7,000+ 张配图**的知识库，
通过 MCP 接进 Claude Code / Codex。**正文能搜，图也能看。**

内容来自五个持续更新的系列，外加一批 GTM playbook：

| 系列 | 篇数 | 特点 |
|---|---|---|
| Lenny's Newsletter | 480 | 产品/增长，可追溯到 2019 |
| Growth Unhinged | 236 | B2B SaaS 增长实操 |
| Marketing Ideas | 198 | 每周营销点子 |
| Fletch PMM | 137 | **Before/After 定位对比**，整页网站截图 |
| MRR Unlocked | 127 | 创始人视角的 GTM |
| Playbooks | 66 | marketingskills、GEO、product launch 等 |

每周六自动扫描更新。

---

## 想用？

仓库是私有的，MCP 也是白名单制。**跟阿蓓（@beizhangnina）说一声**，
她会给你发一套独立凭证，你自己机器上配一次就好。

- 每个人一套独立的 `client_id` / `client_secret`，可以单独撤销，互不影响
- 同事默认只给 `read` —— 写入权限只有 ingest 那个 client 有，
  这样任何人的凭证泄露都不会污染知识库
- **不需要 clone 这个仓库**，也不需要在本地存任何内容

完整步骤见 **[docs/INSTALL-FOR-TEAMMATES.md](docs/INSTALL-FOR-TEAMMATES.md)**，
装好大概两分钟。

---

## 这个仓库是什么

**是**一个 vault 对账器。它只读阿蓓的 Obsidian vault，
不关心 markdown 是谁写进去的（目前是 Grok Bot 在持续抓取更新）。
抓取层以后换成别的，这里一行都不用改。

**不是**爬虫。没有 RSS、没有 IMAP、没有浏览器自动化。

**服务端也不是自己写的** —— 直接用 [garrytan/gbrain](https://github.com/garrytan/gbrain)，
钉在 v0.51.0.0。检索、向量、知识图谱、OAuth、125 个 MCP tool 全是它的。

```
Obsidian vault（只读真源，永不写入）
        ↓
  1. 按 sha256 找出变化的 .md
  2. 图片瘦身 → WebP 衍生品
  3. 内容寻址上传 → Supabase Storage
  4. 正文 ./images/... → 公网绝对 URL
  5. put_page → gbrain
        ↓
  Railway 上的 gbrain HTTP MCP (OAuth)
        ↓
  你的 Claude Code / Codex
```

### 两个核心设计

**vault 存原图，云端存瘦身衍生品。** 同一份 markdown，两种读者：
Obsidian 要相对路径和原始动图，agent 要绝对 URL 和快速加载。
只在 ingest 那一刻做一次链接重写，**vault 文件本身一个字节都不动**。

**全流程幂等对账。** 每一步跑一百遍结果一样，中断随时重跑，
不需要 `--resume` 这种开关。漏跑一次也不丢内容 —— 真源一直在 vault 里。

### 为什么要给图片瘦身

不是为了省钱（存储额度绰绰有余），是为了**能用**：
vault 里最大的图是 36 MB 的 GIF，agent fetch 一张要等很久。

实测 **2,568 MB → 516 MB（省 80%）**，动图能压 200–1000 倍
（取首帧转 WebP —— agent 需要看清内容，不需要动画）。

⚠️ 缩放按**宽度**限制，不是最长边。见
[docs/gotchas.md](docs/gotchas.md) G-001 —— 那个坑会安静地
把整页截图压成 152px 宽，毁掉库里最有价值的 Before/After 对比图。

---

## 自己跑

```bash
cp .env.example .env    # 填 key
uv sync

uv run gtm-brain status    # vault 现状 + 对账进度
uv run gtm-brain slim      # 图片瘦身（并行，只读 vault）
uv run gtm-brain upload    # 传 Supabase Storage
uv run gtm-brain ingest    # 推进 gbrain
uv run gtm-brain failures  # 看失败详情
```

每周六 09:00 PT 由 launchd 自动跑 `bin/weekly-sync`（三步串起来，带单实例锁）。
日志在 `~/Library/Logs/gtm-brain/`。

`state.db` 和 `.cache/` 都是可重建的缓存，删掉重跑即可，里面没有真源。

---

## 文档

- **[docs/INSTALL-FOR-TEAMMATES.md](docs/INSTALL-FOR-TEAMMATES.md)** — 同事接入指南
- [docs/gotchas.md](docs/gotchas.md) — 踩过的坑，**动这个项目前先读一遍**
- [tasks/todo.md](tasks/todo.md) — 实施进度
- [docs/OPERATIONS.md](docs/OPERATIONS.md) — 运维速查：资源标识、发/撤凭证、升级、已知工具坑
- [tasks/lessons.md](tasks/lessons.md) — 经验教训

---

## 内容边界

库里有付费订阅内容（Lenny's 等）。图片托管在公开 bucket 上，
但路径是内容 SHA-256、不可枚举，也设了 `noindex`。

**不要把图片 URL 或正文贴到公开的地方。** 这是给内部几个人用的工具，
不是一个公开镜像。
