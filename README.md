# GTM Brain

一个装着 **1,249 篇 GTM 文章、7,000+ 张配图**的知识库，接进你的 **Claude Code 或 Codex**。
问一句 GTM 问题，它会先去库里找相关原文，再基于原文回答，并告诉你出自哪篇。

> **你不需要 clone 这个仓库，也不需要懂代码。** 装好只要两分钟，从头到尾照下面做就行。

---

## 一、这个库里有什么

六个来源，全是一手的 GTM 实操内容，**每周六自动更新**：

| 来源 | 篇数 | 时间跨度 | 适合找什么 |
|---|---|---|---|
| **Lenny's Newsletter** | 484 | 2019 – 至今 | 产品、增长、PLG、定价、团队与职业；大量访谈和数据 |
| **Growth Unhinged** | 236 | 2021 – 至今 | B2B SaaS 增长实操：免费试用、定价、PLG 转化、指标 |
| **Marketing Ideas** | 199 | 2023 – 至今 | 每周具体的营销打法和案例，拿来就能用的点子 |
| **Fletch PMM** | 137 | — | **网站定位改版前后对比**：改之前哪里不好、改之后好在哪，附整页截图 |
| **MRR Unlocked** | 127 | 2021 – 至今 | 创始人视角的早期 GTM：冷邮件、LinkedIn、销售演示、定位工作表 |
| **Playbooks** | 66 | — | 成体系的手册：定价策略、产品发布、Product Hunt、GEO / AI 搜索优化、各类转化优化 |

文章里的配图（图表、截图、框架图）都保留着，是可以直接打开的链接。

**库里没有的**：实时新闻、某家公司的内部数据、GTM 以外的话题。
问到这些，它会告诉你库里没有，再用自己的知识或网络补充。

---

## 二、找阿蓓要安装文件

仓库是私有的，服务也只对开通了的人开放。**私信阿蓓（Bei Zhang，GitHub [@beizhangnina](https://github.com/beizhangnina)）说一声**，
告诉她你想用，以及你的英文名（比如 `alice`）。

她会发你一个文件：**`你的名字-install.sh`**。

- 这是**只给你一个人用的**：里面有你的个人凭证。**别转发，也别放进群聊、邮件、网盘或 git。**
- 凭证是**只读**的：只能搜和读，改不了库里的东西。
- 通常是 AirDrop 或私聊发给你。**装好之后把那条消息删掉。**

---

## 三、安装（一次，约两分钟）

**需要**：装了 Claude Code 或 Codex（ChatGPT 桌面 App 里那个）其中之一。Mac 自带的 `python3` 就够，不用装别的。

1. 打开 Mac 的 **「终端」（Terminal）** App
2. 进入安装文件所在的文件夹，比如下载目录：
   ```bash
   cd ~/Downloads
   ```
3. 运行（把 `alice` 换成你的名字）：
   ```bash
   bash alice-install.sh
   ```
4. 看到这句就装好了：
   ```
   ✓ 完成，已装进 Claude Code 和 Codex。
   ```
   （只装了其中一个的话，就只显示那一个）

> 必须在「终端」里运行，不要在 Claude Code 的对话框里跑。

**它做了什么**（都只动你自己电脑，而且只动 gtm-brain 相关的那一段，不碰你其他的配置）：

- 把凭证存到 `~/.config/gtm-brain/`，只有你自己能读
- 装了 Claude Code 就配进 Claude Code，装了 Codex 就配进 Codex，两个都有就两个都配
- 在 `~/.claude/CLAUDE.md` / `~/.codex/AGENTS.md` 里加一条规则：**问 GTM 问题时自动先查这个库**
- 凭证会自动续期，**装一次就永远不用管**

---

## 四、怎么用

**先重启一次**：新开一个 Claude Code 会话；用 Codex 的话，**彻底退出并重新打开 ChatGPT App**。

然后**直接用中文或英文问就行，不用提「gtm-brain」**。几个例子，以及你大概会看到什么：

| 你问 | 它会去找的（实测结果） |
|---|---|
| B2B SaaS 首页定位有哪些好的改版案例？给我三个，说说改前改后的区别 | Fletch PMM 的 Survicate、lemlist、Blue Triangle 等改版前后对比 |
| 免费试用怎么优化转化？ | Growth Unhinged 的免费试用优化、reverse trial 指南，MRR Unlocked 的免费试用 8 条要点 |
| 定价策略怎么做？ | Growth Unhinged 的定价项目方法、Playbooks 的定价策略手册、Lenny's 的 B2B 增长引擎 |
| 产品发布前要准备什么？ | Playbooks 的发布策略和 Product Hunt 发布指南 |

**你会得到**：基于原文的回答，带出处（系列 + 文章标题），需要时附上原文里的图片链接。
**中文提问也能搜到英文文章**。每次查库大约 4–6 秒。

**问得越具体，答得越好**。几个好用的问法：

- 「PLG 公司怎么加上销售团队？ClickUp、Calendly 这些是怎么做的」
- 「AI 搜索 / GEO 应该怎么做？有哪些具体步骤」
- 「Fletch PMM 里 fintech 公司的改版案例，总结它们共同的问题」
- 「activation 指标怎么定？列出相关文章，每篇一句话总结」

想确认它连上了：在 Claude Code 里输入 `/mcp`，列表里有 **gtm-brain ✔ connected** 就对了。

---

## 五、遇到问题

| 现象 | 怎么办 |
|---|---|
| 安装时报「凭证换不到 token」 | 凭证可能已经失效。找阿蓓重新发一个安装文件 |
| 安装时报「没找到 Claude Code 也没找到 Codex」 | 先装其中一个，再重新运行安装文件 |
| Claude / Codex 回答时没有去查库 | 1）确认重启过（新会话 / 重开 App）；2）Claude Code 里输入 `/mcp` 看是否 connected；3）实在不行，问的时候加一句「用 gtm-brain 查」 |
| 其他报错 | 在终端运行 `python3 ~/.config/gtm-brain/headers.py`，把输出发给阿蓓（不会显示你的密码） |
| 换了新电脑 | 在新电脑上再运行一次同一个安装文件就行 |
| 不想用了 / 离职 | 告诉阿蓓，她会注销你的凭证，立刻生效 |

---

## 六、使用规范

库里有**付费订阅内容**（Lenny's 等）。这是给内部少数人用的工具，不是公开镜像：

- **不要把正文、图片链接贴到公开的地方**（社交媒体、公开文档、对外材料）
- 引用观点可以，大段复制原文不行
- 安装文件和凭证只给你自己用

更详细的安装说明（原理、每一步做了什么）：[docs/INSTALL-FOR-TEAMMATES.md](docs/INSTALL-FOR-TEAMMATES.md)

---
---

## 给维护者（阿蓓）

> 以下是维护这个服务的人看的。只是使用的话，读到上面就够了。

### 开通 / 注销同事

见仓库根目录 **[`add teammate - for bei.txt`](add%20teammate%20-%20for%20bei.txt)**：
`bin/onboard-teammate <名字>` 生成安装文件，台账记在 `onboarding/clients.log`（已 gitignore）。

### 架构

**这个仓库是一个 vault 对账器**：只读阿蓓的 Obsidian vault（Grok Bot 在持续往里抓取更新），
把变化推进托管的 brain。它不是爬虫。服务端直接用 [garrytan/gbrain](https://github.com/garrytan/gbrain)，钉在 v0.51.0.0。

```
Obsidian vault（只读真源，永不写入）
        ↓
  1. 按 sha256 找出变化的 .md 和图片
  2. 图片瘦身 → WebP 衍生品
  3. 内容寻址上传 → Supabase Storage（新加坡）
  4. 正文 ./images/... → 公网绝对 URL
  5. 渲染结果变了才 put_page → gbrain
        ↓
  Railway 上的 gbrain HTTP MCP（新加坡，与数据库同区）
        ↓
  用户的 Claude Code（headersHelper）/ Codex（本地 stdio 桥接）
```

- **vault 存原图，云端存瘦身衍生品**：只在 ingest 时重写链接，vault 文件一个字节都不动。
  图片 2,568 MB → 516 MB（省 80%）；缩放按宽度限制，不是最长边（见 gotchas G-001）。
- **全流程幂等**：每一步跑一百遍结果一样，中断随时重跑。是否重推按「实际推送的内容」判断（G-014）。
- **Railway 必须和 Supabase 同区**：跨区时每页写入占锁 ~60s，会连锁卡死（G-013）。

### 日常运维

```bash
uv sync
uv run gtm-brain status    # vault 现状 + 对账进度
bin/weekly-sync            # slim → upload → ingest，全部幂等
```

每周六 09:00 PT 由 launchd 自动跑 `bin/weekly-sync`，日志在 `~/Library/Logs/gtm-brain/`。
正常一次周更约 15 秒；**超过 10 分钟一定有问题**，按 OPERATIONS.md 的排查顺序查。

### 文档

- [docs/OPERATIONS.md](docs/OPERATIONS.md) — 运维速查：资源标识、每周 runbook、排查顺序、换数据库密码、已知工具坑
- [docs/gotchas.md](docs/gotchas.md) — 踩过的坑，**动这个项目前先读一遍**
- [docs/INSTALL-FOR-TEAMMATES.md](docs/INSTALL-FOR-TEAMMATES.md) — 用户安装的详细说明
- [tasks/todo.md](tasks/todo.md) — 实施进度 · [tasks/lessons.md](tasks/lessons.md) — 经验教训
