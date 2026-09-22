# gtm-brain 实施清单

计划全文：`~/.claude/plans/obsidian-folder-01-projects-dormy-gtm-enchanted-sonnet.md`

## Phase 0 — 清理 + 地基

### 需要阿蓓操作（我做不了）
- [ ] `railway login`
- [ ] `bun upgrade`（1.3.10 → ≥1.3.11）
- [x] 往 `.env` 填 `VOYAGE_API_KEY` ✅ 三个端点已实测通过
- [ ] 往 `.env` 填 `SUPABASE_URL` + `SUPABASE_SERVICE_KEY`

### 清理旧资源（登录后我来跑，逐条确认）
- [x] ~~pg_dump 备份~~ —— 阿蓓已自行删除该 project，无法备份
- [ ] 列出 Railway 项目清单，逐条确认后删除（保留 `frontiertracker` / `dormy-ai`）
- [x] Supabase `dormy-brain` 已删（阿蓓操作），`dormy` 完好保留 ✅
- [ ] dormy-ai 的 Railway 上 unset `DORMY_BRAIN_DATABASE_URL`

### 地基
- [x] 建工作目录 + `.env` / `.env.example` / `.gitignore`
- [x] Python 包骨架 + `pyproject.toml`
- [ ] `gh auth switch --user beizhangnina`
- [ ] `gh repo create beizhangnina/gtm-brain --private` + 首次 push
- [x] **改用 Supabase Postgres**（Pro 自带每日备份 + PITR，比 Railway Postgres 强）
      新建 project `gtm-brain`（新加坡，ref `bfcmhbgbomlygoeahhli`），
      PG 17.6 + pgvector 0.8.2 + pg_trgm + pgcrypto 已装，session pooler 拨测通过
- [x] bucket `gtm-assets` 已建，public read
- [x] **Smoke 通过**：公网 URL 免鉴权 200，Claude 能读出 Slack 截图里的表格和小字

## Phase 1 — 图片瘦身与上传（不依赖任何外部服务，可先做）
- [x] `vault.py`：扫描 + sha256 变更检测
- [x] `images.py`：按**宽度** 1600px 缩放 → WebP q80；GIF 取首帧；小图不许膨胀
- [x] `state.py`：SQLite 存 file sha256 / image manifest / ingest 进度
- [x] 小样验证：画质肉眼确认通过（裁图看过，小字清晰）
- [x] `storage.py` + `upload` 命令，**全量上传完成：7,260/7,260 条引用有 URL**
- [x] 全量瘦身：7,260/7,266（6 个是 grokbot 存坏的非图片文件）
- [x] **2,568 MB → 516 MB，省 80%**，去重后 6,739 个唯一衍生品
- [x] 幂等性确认：第二遍 3.7s，零新增工作

## Phase 2 — 索引与服务
- [x] `deploy/` 三件套写完，钉 gbrain **v0.51.0.0** (`d13aa74`)
- [x] 部署到 Railway（~~新加坡区~~ 实际是 us-west2，2026-09-22 才改到新加坡，见 G-013），`/health` 返回 `{status:ok, version:0.51.0.0, engine:postgres}`
- [x] 154 个 migration 应用完成，schema v159，`takes.embedding` 确认 vector(1024)
- [x] `brain.py` + `notes.py` + `ingest` 命令（dry-run 已验证，**等 brain 部署才能实推**）
- [x] **端到端通过**：Fletch PMM / Kolleno 推入后回读，正文含 4 个绝对 URL，
      从 URL 取图肉眼确认整页截图文字清晰
- [x] 全量 ingest 完成：**1,249/1,249，失败 0**（2026-09-22）。最后 45 篇在换区后 38 秒跑完（G-013）
- [x] 页数对账：服务端 `pages` 1,249 = vault 1,249；7,275 个 chunk 全部有 embedding
      （`get_stats` 要 admin scope，改为直接只读查库）

## Phase 3 — 多模态索引（2026-09-22 阿蓓决定：不做）
只需要用文字找内容，不需要以图搜图。图片 URL 已经在正文里，agent 找到笔记后照样能看图。
Fletch PMM 的笔记正文已有 before/after 对比和分析的文字，OCR 边际收益低。
**什么时候再考虑**：实际使用中出现「截图里有这个词、文字搜不到」时，只给 Fletch PMM 开 OCR。

## Phase 4 — 接入与自动化
- [x] `docs/INSTALL-FOR-TEAMMATES.md`
- [ ] **先配到阿蓓自己机器上**（防荒废）
- [ ] 每人一个 OAuth client（read scope）
- [x] launchd 每周六 09:00 对账（`bin/weekly-sync`，runbook 见 OPERATIONS.md）
- [ ] 修存量问题：11 个死图链 / HTML title 后缀 / Growth Unhinged 的 12 处裸 `images/`

## 当前卡点（需要阿蓓操作）

1. ~~**换数据库密码**~~ ✅ 2026-09-22 已完成 —— 我用 `railway variables` 查变量时把完整连接串打进了对话。
   试过用 SQL 轮换，但 Supabase 的 `postgres` 角色不是超级用户，改不了自己。
   → https://supabase.com/dashboard/project/bfcmhbgbomlygoeahhli/settings/database
   Reset database password，然后告诉我，我更新 `.env` + Railway 变量。
2. ~~**删三个旧 Railway 项目**~~ ✅ 已由阿蓓在 dashboard 删除 —— `railway delete` 用项目名和完整 UUID 都报
   "not found"，但 `railway list` 列得出来，workspace 也只有一个。CLI 自身问题。
   - dormy-brain `4afd337e-d6e9-4677-a6e2-b098d7da846a`
   - vibe-trading `cf37f380-6dc5-438f-885e-4ae794f53ea0`
   - nanobot `705b2bf1-eeab-45b8-a52b-fb587c553fe1`

## 已解决的卡点

- **Supabase key** → 才能跑 `upload`
- **`railway login`** → 才能列项目清单做清理、才能部署 brain

## 发现的数据质量问题（不阻塞，但值得修）

1. **grokbot 把 HTTP 错误响应当图片存了** —— 6 个文件：4 个 11 字节内容是
   `Bad Request`，2 个 130 字节是纯 URL 文本，扩展名都是 `.gif`。
   建议 grokbot 下载时校验 status code + content-type 再落盘。
   占比 6/7,266 = 0.08%，数据质量整体很好。
2. **31 处死图链集中在 6 篇笔记** —— 最多的是
   `Playbooks/GEO红皮书…md`（15 处）和
   `Newsletters/Marketing Ideas/2026-04-20 How to get leads from your 404 page…md`（11 处，
   指向已不存在的 `04-GTM/`，原图确实没了，要靠 grokbot 重抓）。
   对账器**原样保留**这些链接，不擅自吞掉。

## Review（Phase 1–2，2026-09-22）

**做了什么**：vault → 图片瘦身（2.57GB → 516MB）→ Supabase 存储 → gbrain MCP（Railway）；
1,249 篇笔记、7,260 条图片引用全部入库，每周自动对账。

**偏离计划的地方**：
- 全量回填花了约两天，而不是计划的 6 小时。根因是 Railway 实际部署在 us-west2、数据库在新加坡，
  每页写入占锁 ~60s 导致连锁卡死（G-013）。换区后速度快了约 70 倍。
- 中途两次崩溃：连接层异常没重试（G-011）、启动阶段 token 超时（G-012）。

**遗留项**：
- ~~换 Supabase 数据库密码~~ ✅ 2026-09-22 已轮换（`bin/rotate-db-password`），端到端验证通过。
- Phase 3（图片多模态索引）、Phase 4 剩余（配到自己机器、每人一个 OAuth client、修存量死图链）。
