# 运维速查

> 这些都不是密钥，是资源标识。真正的密钥在本地 `.env`（已 gitignore）
> 和 Railway dashboard 里，按「单向流动」原则走：
> 签发方 → 1Password → 部署平台，不经过对话、不进 git。

## 线上资源

| 资源 | 标识 |
|---|---|
| MCP endpoint | `https://gtm-brain-production.up.railway.app/mcp` |
| 健康检查 | `https://gtm-brain-production.up.railway.app/health` |
| Railway project | `gtm-brain` · `eff2b1c1-c012-41cc-ae3b-c628950faa72` · service 区域 **`asia-southeast1-eqsg3a`（新加坡，写死在 railway.toml）** |
| Supabase project | `gtm-brain` · ref `bfcmhbgbomlygoeahhli` · 新加坡 |
| Storage bucket | `gtm-assets`（public read，路径是内容 SHA-256） |
| gbrain 版本 | v0.51.0.0 · `d13aa742fd68b71bfd6c98be3dda5813791f1d6c` |
| Embedding | `voyage:voyage-4` @1024 / 图片 `voyage:voyage-multimodal-3` @1024 |
| LLM（think 综合 + query 扩展） | `deepseek:deepseek-v4-flash`，base_url 改到 flatkey（`https://router.flatkey.ai/v1`）；Railway 变量 `DEEPSEEK_API_KEY` = flatkey 的 gtm-brain 专用 key。一次 think 约 $0.005、1–3 分钟。换模型设 `GTM_BRAIN_LLM_MODEL` |

## 常用操作

**给同事发凭证**（只给 read）：
```bash
railway ssh -s gtm-brain bun /app/src/cli.ts auth register-client <名字> \
  --grant-types client_credentials --scopes read
```
> ⚠️ `--scopes` 要用逗号分隔。`"read write"` 会被 railway ssh 按空格拆成两个参数。
> 输出里有 client_secret，**别直接打印到终端或对话**，重定向到文件再处理。

**撤销某人**：
```bash
railway ssh -s gtm-brain bun /app/src/cli.ts auth revoke-client <名字>
```

**看服务日志**：`railway logs -s gtm-brain`

**升级 gbrain**：改 `Dockerfile` 里的 `GBRAIN_SHA` 一行，然后 `railway up -s gtm-brain`。
> 升级前务必确认新版本的 `embedding_dimensions` 默认值 —— 它在 initSchema
> 之前就决定向量列宽，跟现有的 1024 不一致会要求重建整库。

**改定时**：`launchd/ai.gtm-brain.weekly.plist`，改完
`cp` 到 `~/Library/LaunchAgents/` 再 `launchctl unload && load`。
当前是每周六 09:00 PT（本机就在 PT 时区；**换时区要改这里**）。

## 每周更新 runbook

**自动**：launchd 每周六 09:00 PT 跑 `bin/weekly-sync`（slim → upload → ingest），
三步都按内容 sha256 幂等，只处理新增/改动的笔记和图片。日志在
`~/Library/Logs/gtm-brain/sync-*.log`（保留最近 20 份）。

**正常情况下的量级**（2026-09-22 换区后实测）：全量重推 1,249 篇用了 17 分钟（约 73 篇/分钟）；
一次什么都没变的周更 **约 15 秒**，补推 18 篇也在这 15 秒内。
如果一次周更跑了超过 10 分钟，**一定有问题，别等**。

**手动跑 / 检查，按这个顺序**：
```bash
bin/weekly-sync                         # 或者单跑某一步：uv run gtm-brain ingest --workers 4
tail -30 "$(ls -t ~/Library/Logs/gtm-brain/sync-*.log | head -1)"
sqlite3 state.db "select count(*), sum(ingested_at is not null), sum(error is not null) from notes"
```
失败的篇目不用单独处理：`error` 不为空的会在下一次 ingest 自动重推（写入按 request_id 幂等）。

**跑得慢 / 卡住时的排查顺序**（G-013 的经验，20 分钟内定位）：
1. `curl .../health` —— 服务活着吗。
2. **核实区域**：`railway status --json` →
   `latestDeployment.meta.serviceManifest.deploy.multiRegionConfig` 必须是
   `asia-southeast1-eqsg3a`。任何一次 Railway 侧的重建/迁移都可能把它弄回 us-west2。
3. 采样 `pg_stat_activity`（`application_name='Supavisor' and state<>'idle'`，每 5s 一次）：
   看到 `wait_event='ClientRead'` 且 `xact_start` 超过几秒的事务 = 服务端拿着锁在等别的东西
   （跨区延迟、服务端 CPU、外部 API）。`pg_blocking_pids()` 看谁挡着谁。
4. 报错原文直接 grep gbrain 源码（钉住的版本见上表），看它在什么条件下抛出。

**并发**：服务端对同一个 source **严格串行**写入，客户端 `--workers` 开多了没有用，只会多抢锁。
保持 4（G-010 的旧测量数据在跨区时代测的，已作废；换区后没重新测，因为周更的量太小，测不出区别）。

## 轮换数据库密码

1. Supabase dashboard → Reset database password（`postgres` 角色不是超级用户，SQL 改不了）。
2. 自己的终端里跑 `bin/rotate-db-password`，粘贴新密码。脚本会先验证新密码能连上库，
   再更新 `.env` 和 Railway 变量（`--stdin`，密码不进进程参数），最后等服务重新上线。
   连不上就什么都不改。

## 已知的工具坑

- **`railway delete` 用项目名和完整 UUID 都报 "not found"**，但 `railway list`
  列得出来、workspace 也只有一个。删项目请用 dashboard。
- **`railway variables` 的输出会把变量值完整打印出来**，包括数据库连接串。
  只想看变量名的话，grep `^║ *[A-Z_]+` 而不是按列取。
  （这个坑实际泄露过一次密码，导致要轮换。）
- **Supabase 的 `postgres` 角色不是超级用户**，`ALTER ROLE postgres WITH PASSWORD`
  会被拒。换密码只能在 dashboard 的 Settings → Database → Reset database password。
- **换区域别用 toml 也别用 `railway scale`**：前者不覆盖环境配置，后者在 4.30.3 里 panic。
  用 GraphQL `serviceInstanceUpdate` 改，然后 `railway up`（**不是** `redeploy`，redeploy 复用旧配置快照）。见 G-013。
- **`railway ssh` 传参会按空格拆分**，带空格的参数要换成逗号或别的分隔方式。
