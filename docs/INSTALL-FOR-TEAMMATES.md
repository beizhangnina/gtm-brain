# 接入 GTM Brain

一个装着 1,200+ 篇 GTM newsletter 和 7,000+ 张配图的知识库，
通过 MCP 接进你的 **Claude Code 和 / 或 Codex**，用文字就能搜。

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

## 第 1 步：找阿蓓要安装脚本

每个人一套独立的只读凭证，能单独撤销，互不影响。阿蓓那边跑：

```bash
bin/onboard-teammate <你的名字>
```

会生成一个 `<你的名字>-install.sh`，她会 AirDrop 或私聊发给你。**装好后把那条消息删掉。**
**这个文件里有你的个人凭证，别转发、别提交到任何地方。**

## 第 2 步：跑一次

```bash
bash <你的名字>-install.sh
```

它会自动检测你装了什么，**Claude Code、Codex 都有就两个都装**：

| | Claude Code | Codex（ChatGPT App） |
|---|---|---|
| 怎么连 | `headersHelper`：每次连接时自动换新 token | 本地 stdio 桥接 `stdio_bridge.py`：每次请求自动换新 token |
| 写到哪 | `claude mcp add-json`（user 级，所有项目可用） | `~/.codex/config.toml` 里的 `[mcp_servers.gtm-brain]` |
| 全局规则 | `~/.claude/CLAUDE.md` | `~/.codex/AGENTS.md` |

两边连的是**同一个 brain、同一份凭证**（存在 `~/.config/gtm-brain/.env`，权限 600）。
**配一次就永远不用管**，不会一小时后过期。

「全局规则」是一小段指令：问 GTM 相关问题时，Claude / Codex 会自动先查 gtm-brain，
**不用每次都说「用 gtm-brain」**。它写在带标记的一段里，重装只替换这一段，不碰你原有的内容。
配置文件里也一样，只动 `gtm-brain` 那一段。

需要：装了 Claude Code 或 Codex 其中之一，机器上有 `python3`（macOS 自带）。不需要 clone 任何仓库。

> 为什么不是普通的 `claude mcp add ... http`：gbrain 的浏览器授权会跳到管理员同意页，
> 同事进不去。所以改用 client_credentials + headersHelper，完全不走浏览器。

## 第 3 步：验证装好了

**重开一个** Claude Code 会话，或者**重启 ChatGPT App**（MCP 在启动时加载），直接问：

> B2B SaaS 首页定位有哪些好的改版案例？给我三个，说说改前改后的区别

装好的话，它会返回带引用的正文。正文里的图片都是可以直接打开的链接。

---

## 怎么用它才有价值

这个库的强项是**一手的 GTM 实操细节**，不是泛泛的框架。几个好用的问法：

- 「Fletch PMM 里有哪些 fintech 的 Before/After？把改动前后的定位差异总结给我」
- 「Lenny's 里关于 PLG 到 sales-led 转型的文章，按时间排一下，看观点怎么变的」
- 「找 2026 年提到 AI 搜索 / GEO 的所有内容」—— 每页都打了 `year:` tag

按 tag 过滤：`series:lennys-newsletter`、`series:fletch-pmm`、
`source:newsletter`、`source:playbook`、`year:2026`、`industry:fintech`。

---

## 出问题时

| 现象 | 原因 |
|---|---|
| 安装脚本报「凭证换不到 token」 | 凭证被撤销或网络不通。找阿蓓重新生成 |
| Claude Code 里 `/mcp` 显示 gtm-brain 连不上，或 Codex 里没有 gtm-brain 工具 | 在终端跑 `python3 ~/.config/gtm-brain/headers.py`，报错信息发给阿蓓 |
| `insufficient_scope` | 你在调一个需要 `admin` 或 `write` 的工具。同事只有 `read`，正常 |
| 图片打不开 | 图片是公开 URL，不需要凭证。打不开说明是网络问题，不是权限问题 |

---

## 关于图片

正文里的图片是**瘦身过的 WebP**，存在 Supabase Storage 上，URL 是内容哈希、
不可枚举。原图留在阿蓓的 Obsidian vault 里，没动过。

这些内容来自付费订阅（Lenny's 等）。URL 不可猜、不被搜索引擎收录，
但**请不要把它们贴到公开的地方**。
