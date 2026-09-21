# 接入 GTM Brain

一个装着 1,200+ 篇 GTM newsletter 和 7,000+ 张配图的知识库，
通过 MCP 接进你的 Claude Code / Codex。**正文能搜，图也能看。**

内容来源：Lenny's Newsletter、Growth Unhinged、Marketing Ideas、
Fletch PMM（Before/After 定位对比）、MRR Unlocked，外加一批 GTM playbook。
每周自动更新。

---

## 先搞清楚一件事

这是**一个** MCP server，不是两个：

| 名字 | 是什么 |
|---|---|
| `gtm-brain` | 你要装的 MCP server，地址 `https://gtm-brain-production.up.railway.app/mcp` |
| `beizhangnina/gtm-brain` | 维护它的代码仓库。**你不需要 clone**，装 MCP 跟仓库无关 |

---

## 第 1 步：找阿蓓要一份凭证

每个人一套独立凭证，能单独撤销，互不影响。跟阿蓓说一声，她会跑：

```bash
railway ssh -s gtm-brain bun /app/src/cli.ts auth register-client <你的名字> \
  --grant-types client_credentials --scopes read
```

你会拿到两个值：`client_id`（`gbrain_cl_…`）和 `client_secret`（`gbrain_cs_…`）。

> 同事默认只给 `read`。写入权限只有 ingest 用的那个 client 有 ——
> 这样任何人的凭证泄露都不会污染知识库。

## 第 2 步：把凭证存在自己机器上

```bash
mkdir -p ~/.config/gtm-brain
cat > ~/.config/gtm-brain/.env <<'ENV'
GTM_BRAIN_URL=https://gtm-brain-production.up.railway.app
GTM_BRAIN_CLIENT_ID=<你的 client_id>
GTM_BRAIN_CLIENT_SECRET=<你的 client_secret>
ENV
chmod 600 ~/.config/gtm-brain/.env
```

凭证存在**你自己**机器上，server 不保存谁在用它。

## 第 3 步：接进客户端

**Claude Code**

```bash
claude mcp add gtm-brain -s user -t http https://gtm-brain-production.up.railway.app/mcp
```

首次调用时会走 OAuth 授权。

**Codex** —— 在 `~/.codex/config.toml` 里加：

```toml
[mcp_servers.gtm-brain]
url = "https://gtm-brain-production.up.railway.app/mcp"
```

## 第 4 步：验证装好了

在 Claude Code 里问一句：

> 用 gtm-brain 搜一下 B2B SaaS 的定位框架，给我三个案例

装好的话，它会返回带引用的正文。**再让它描述其中一张图** ——
能描述出来，说明图片链路也通了（这是这个库跟普通 RAG 最大的区别）。

---

## 怎么用它才有价值

这个库的强项是**一手的 GTM 实操细节**，不是泛泛的框架。几个好用的问法：

- 「Fletch PMM 里有哪些 fintech 的 Before/After？把改动前后的首屏文案对比给我」
  —— 这些是整页网站截图，Claude 能直接读出上面的文案
- 「Lenny's 里关于 PLG 到 sales-led 转型的文章，按时间排一下，看观点怎么变的」
- 「找 2026 年提到 AI 搜索 / GEO 的所有内容」—— 每页都打了 `year:` tag

按 tag 过滤：`series:lennys-newsletter`、`series:fletch-pmm`、
`source:newsletter`、`source:playbook`、`year:2026`、`industry:fintech`。

---

## 出问题时

| 现象 | 原因 |
|---|---|
| 401 / `invalid_client` | 凭证不对，或者被撤销了。找阿蓓重发 |
| `insufficient_scope` | 你在调一个需要 `admin` 或 `write` 的工具。同事只有 `read`，正常 |
| 搜索很慢（10s 左右） | 正常。每次查询要打一次 embedding API，server 在新加坡、embedding 在美国 |
| 图片打不开 | 图片是公开 URL，不需要凭证。打不开说明是网络问题，不是权限问题 |

---

## 关于图片

正文里的图片是**瘦身过的 WebP**，存在 Supabase Storage 上，URL 是内容哈希、
不可枚举。原图留在阿蓓的 Obsidian vault 里，没动过。

这些内容来自付费订阅（Lenny's 等）。URL 不可猜、不被搜索引擎收录，
但**请不要把它们贴到公开的地方**。
