# Gotchas

> 踩过的坑。每条写清楚：**现象 → 原因 → 对策**。

## G-001：整页截图不能按「最长边」缩放

**现象**：Fletch PMM 的 `zebeyond-before.png`（1000x10506）瘦身后变成 `152x1600`，
宽度只剩 152px，文字完全不可读。

**原因**：最初用 `Image.thumbnail((max_edge, max_edge))` 按最长边限制。对整页
网站截图这种 1:5 ~ 1:10 的长图，被限制的是高度，宽度被连带压到几乎为零。

**为什么严重**：全库 **5% 是这类长图**（实测 800x4205 ~ 1889x8391），而 Fletch PMM
的 Before/After 对比图恰恰是整个知识库里信息密度最高的内容。这个 bug 不会报错、
不会失败，只会安静地毁掉最有价值的那部分。

**对策**：按**宽度**限制，不是最长边（`DEFAULT_MAX_WIDTH = 1600`）。宽度决定文字
可读性，高度不决定。另设 `DEFAULT_MAX_HEIGHT = 12000` 兜底（WebP 单边硬上限 16383）。
实测全库宽度 p50=1456 / p90=1456 / max=2820，所以 1600 对绝大多数图根本不触发。

**验证方式**：不要只看数字，**裁一块文字区域出来用眼睛看**。

## G-002：小图转 WebP 会反向膨胀

**现象**：一张 84KB 的 PNG 转 WebP q80 后是 84.1KB —— 白转一道，还多一次画质损失。

**原因**：已经压得很好的小图，WebP 没有额外空间可榨。

**对策**：`slim()` 里加「不许变大」保护 —— 若产出 ≥ 源文件 95% 且源本来就是
网页原生格式（png/jpg/webp）且 ≤ 400KB，则原样透传。实测 200 张样本里触发 10 次。

## G-003：Supabase Storage 的 HEAD 响应不反映真实 cache-control

**现象**：上传时设了 `Cache-Control: public, max-age=31536000, immutable`，
`curl -I`（HEAD）却返回 `cache-control: no-cache`，看起来像没生效。

**真相**：设置是生效的。HEAD 和 GET 返回不同的 cache 头 ——
`GET` 返回 `public, max-age=31536000`，`POST /object/list` 查到的存储元数据也是
`public, max-age=31536000, immutable`。只有 HEAD 恒返回 `no-cache`。

**对策**：**验证缓存头要用 GET，不要用 HEAD。** 另外只有 `Cache-Control`
这个标准 header 名有效，`cacheControl`（驼峰）和 multipart 的 `cacheControl`
表单字段都会被忽略（实测写进去变成 `no-cache`）。

**代价**：为这个假象排查了 6 种 header 写法。教训是排查前先确认观测手段本身可靠。

## G-004：slug 必须全库唯一，否则 put_page 静默覆盖

**现象**：最初的 slug 规则是 `<series前缀><标题slug>`，不含日期。
实测全库 1,244 篇里有 **3 组撞车、涉及 13 篇**，最严重的是
Lenny's 的 **9 篇**都叫 "Taking the week off"（不同年份的休刊通知）——
它们会塌缩成同一个 slug，gbrain 的 `put_page` 按 slug upsert，
结果是 8 篇被**静默覆盖**，没有任何报错。

**另一类**：中文标题被 `slugify` 剥光后极易撞车 ——
`GEO白皮书-AI搜索时代…` 和 `GEO红皮书-生成式引擎…` 都会变成 `playbook-geo-`。

**对策**：
1. 有日期的笔记，slug 带上日期：`lennys-2024-03-19-taking-the-week-off`。
   日期是天然消歧符，还让 slug 可排序。
2. slugify 丢掉大部分信息时（`_lossy()`：有效字符 < 原标题 30%），
   追加 `rel_path` 的 6 位 sha256 —— 确定性、稳定、只在必要时才变丑。
3. **ingest 前做全局唯一性校验**，撞了就报错中止，绝不静默覆盖。

修完：1,244 篇 → 1,244 个唯一 slug。

**教训**：任何「按业务 key upsert」的写入，都要先证明那个 key 在全量数据上唯一。
"标题看起来都不一样" 是直觉，不是证据。

## G-005：容器里必须 `--bind 0.0.0.0`

**现象**：`gbrain serve --http --port $PORT --public-url https://…` 启动成功，
日志一切正常，但外部请求全被拒、Railway healthcheck 过不了。

**原因**：gbrain **v0.34.1 起默认 bind `127.0.0.1`**。容器里那样绑
等于只有容器自己能连，Railway 的反向代理够不到。

gbrain 自己会告警，但它混在一堆正常启动日志里很容易被略过：
> `WARNING: --public-url is set but --bind is not. Default bind changed to
> 127.0.0.1 in v0.34.1; remote clients reaching the public URL will be refused.`

**对策**：entrypoint 里显式 `--bind 0.0.0.0`。

## G-006：Railway 只认仓库根的 Dockerfile

**现象**：Dockerfile 放在 `deploy/`，`railway.toml` 里写
`builder = "DOCKERFILE"` + `dockerfilePath = "deploy/Dockerfile"`，
Railway 仍然忽略它、走 Railpack 自动探测，然后 `railpack prepare exited with an error`。

**对策**：Dockerfile 放仓库根。`railway.toml` 的 `dockerfilePath` 指向根即可。

## G-007：`.railwayignore` 必须显式排除 `.env`

`railway up` 会把当前目录打包成构建上下文。`.gitignore` 对它无效 ——
**必须在 `.railwayignore` 里单独排除 `.env`**，否则密钥进构建层。
顺带也要排除大文件（本项目 `.cache/` 有 495MB 衍生品）。

## G-008：gbrain 的 put_page 是【异步】的，且对未知参数静默成功

三个叠在一起的坑，合起来能造出一堆「写了但其实没写」的假阳性。

**(1) 参数猜错了它不报错。** 我按直觉传了 `body` / `title` / `tags` /
`frontmatter`，`put_page` 返回成功 —— 但 `get_page` 是 `page_not_found`。
真实契约是 `required: ['slug', 'content']`，`content` 是**带 YAML frontmatter
的完整 markdown**（整页替换），tags 写在 frontmatter 里，没有独立参数。
覆盖已有页要 `force: true` 或传 `expected_revision`。

**(2) 错误藏在 `result.isError` 里，不在 JSON-RPC 的 `error` 里。**
HTTP 200、`jsonrpc` 无 `error`，只看 `"error" in resp` 会把失败当成功。
必须查 `result.isError` + `content[0].text` 里的 JSON 错误体。

**(3) v0.51 起写入是异步的。** put_page 先回
`{"error":"write_pending", "write_request":{...,"retry_after_ms":1000}}`，
真正落库在后台。契约是**用同一个 `request_id` 和同样的参数重试**直到不再 pending
（request_id 保证重试幂等，不会写两遍）。

**对策**：`brain.put_page_sync()` 一次性封装三件事 —— 正确参数、错误双查、
按 `retry_after_ms` 轮询到落库。

**教训**：**写完必须回读验证。** 这三层里任何一层都能让「成功」是假的，
而三层叠在一起时，光看返回值根本发现不了。

## G-009：解析错误体之前不要截断它

`mcp_error()` 一开始把错误文本截到 400 字符再返回，调用方拿去 `json.loads`
直接炸（`Unterminated string`）——而那个 JSON 里正好装着判断是不是
`write_pending` 所需的信息。截断留到最终抛异常时再做。

## G-010：ingest 并发的甜点是 4，不是越多越好

实测同一台机器、同一个 brain：

| workers | 吞吐 |
|---|---|
| 1 | 1.4 篇/分钟 |
| **4** | **3.2 篇/分钟** ← 甜点 |
| 6 | 1.3 篇/分钟（比单线程还差） |
| 8 | 触发大量 `storage_error`（20 篇失败 16 篇，当时还没做重试） |

单篇固定开销约 40s。~~当时归因于 Voyage embedding 往返~~ ——
**这个归因是错的**，真正原因是 Railway 实际跑在 us-west2、数据库在新加坡，
见 G-013。当时以为「Railway 在新加坡」是因为 project 默认区域写着 southeast，
但 service 实例被放在了 us-west2，没人核实过。

超过 4 路并发后，写入准入开始争用，净吞吐反而下降。
（G-013 之后这组数字作废，需要重测。）

**测吞吐时注意**：进程启动要先 sha256 扫描全部笔记（约 60–90s），
测量窗口落在这一段会得到严重偏低的数字。第一次测 6 worker 得到
0.7 篇/分钟就是这么来的，热机后重测才是 1.3。

## G-011：长跑 ingest 要把连接层异常也当成可重试

`put_page_sync` 最初只重试 gbrain **返回**的业务错误
（`write_pending` / `storage_error`），漏了 httpx **抛出**的连接异常。
实测 450 篇里有 5 篇栽在 `RemoteProtocolError: Server disconnected` 上 ——
跑几小时的任务，服务端偶尔断连是必然的。

**能安全重试的前提**：写入由 `request_id` 保证幂等。
即使服务端其实已经收下了这次写入，用同一个 request_id 重发也不会写两遍。
没有这个保证的话，盲目重试会造成重复数据。

覆盖：`RemoteProtocolError` / `ReadTimeout` / `WriteTimeout` /
`ConnectTimeout` / `ConnectError` / `ReadError` / `WriteError` / `PoolTimeout`，
指数退避，最多 6 次。

## G-012：一次启动阶段的超时，崩掉了跑了 11 小时的任务

**现象**：给 `put_page_sync` 加完网络重试后重启 ingest，进程「启动成功」，
但实际在启动阶段就崩了、一篇没跑。栈是
`cli.py:310 in ingest → brain.py:74 in token` → `ReadTimeout`。

**原因**：重试只加在了 `put_page_sync` 内部，而启动时的
`bc.token()` / `bc.initialize()` 是裸调用。一次 OAuth token 取不到，
整个进程直接退出。

**更深的教训（两条）**：
1. **凡是走网络的调用都要包重试，不只是主循环里那个。**
   现在有 `brain.with_network_retry()` 通用封装。
2. **重启后必须确认它真的在动，不能看到「进程已启动」就走人。**
   当时的验证命令被转到后台，输出没被读，于是崩溃悄无声息 ——
   等再看进度时才发现数字纹丝不动。
   **验证要看"进度有没有增长"，不是"进程在不在"。**

## G-013：服务端和数据库跨太平洋，一页写入占锁 60 秒，连锁卡死

**现象**：全量 ingest 越跑越慢（每小时 79 → 51 → 37 → 16 → 8 篇），
并且反复出现整段 20–34 分钟**一篇都进不去**的停顿，失败信息是
`storage_error: Write admission is temporarily blocked by database contention`。
我一开始把它当成「Supabase 那边的锁争用、只能等」—— **这是错的，没查根因就下了结论。**

**怎么查出来的**（下次照这个顺序，20 分钟能定位）：
1. 在 gbrain 源码里 grep 报错原文 → `src/core/persistence/admission-retry.ts`。
   它只在 Postgres 返回 `40001/40P01/55P03/57014`（序列化冲突/死锁/拿不到锁/语句超时）
   且 5 秒内重试不成功时才抛这个错。所以是**锁**，不是容量。
2. 直连数据库每 5s 采样 `pg_stat_activity` + `pg_blocking_pids()`
   （脚本思路：只看 `application_name='Supavisor' and state<>'idle'`）。看到：
   - 任意时刻只有**一个**长事务在写页面（`INSERT pages → tags → content_chunks → page_aliases`），
     持续 ~60s；
   - 每条 SQL 自身耗时 0s，事务的时间全耗在语句之间的 `ClientRead` ——
     **数据库在等服务端发下一条**；
   - 被它挡住的有：写入租约续期 `UPDATE persistence_requests SET claim_expires_at`、
     过期回收 `SET state='queued'`、甚至 OAuth 取 token 的 `SELECT oauth_clients`。
3. 读 `consumer.ts`：同一 source 同一时刻只写一页（`activeRoots` 按 source 串行），
   写入租约 `leaseMs = 30_000`。
4. `railway status --json` 看 `serviceManifest.deploy.multiRegionConfig` → **`us-west2`**；
   数据库 host 是 `aws-0-ap-southeast-1.pooler.supabase.com`（新加坡）。

**因果链**：每页一个事务里几百条顺序 SQL × 跨太平洋 ~170ms RTT ≈ 60s 占锁
→ 超过 30s 租约 → 租约过期被回收、同一页被重做（昨天日志里同一页出现两次就是这个）
→ 续期、回收、准入、取 token 全排在那行锁后面 → 整段卡死。
**客户端开几个 worker 都没用**：服务端对同一 source 是严格串行的，
多开只是多抢那行全局计数器（`persistence_counters` 里 key='brain'）的锁。

**修复**：service 挪到 `asia-southeast1-eqsg3a`，跟 Supabase 同区。
service 没挂 volume（`/data` 是启动时生成的配置，OAuth client 在库里），
换区就是一次重新部署，无数据迁移。

**结果**（2026-09-22 实测）：

| | 换区前（us-west2） | 换区后（新加坡） |
|---|---|---|
| 单页写入事务 | ~60s | 采样 5s 间隔内看不到长事务 |
| 吞吐 | 0.6–1 篇/分钟，间歇整段卡死 | **45 篇 / 38 秒 ≈ 70 篇/分钟** |
| 失败 | 反复出现 900s 超时 | 0 |

服务端核对：`pages` 1,249 行 = vault 1,249 篇；`content_chunks` 7,275 个，
`embedding is null` 为 0。

**换区本身踩的三个坑**（下次别再绕）：
1. **`railway.toml` 里写 `multiRegionConfig` 不生效。** 部署元数据里能看到文件提供了这个字段，
   但环境级配置（`environment.config.services.<id>.deploy.multiRegionConfig`）里的 us-west2 优先。
   必须用 GraphQL 改环境配置：
   `serviceInstanceUpdate(serviceId, environmentId, input:{multiRegionConfig:{"asia-southeast1-eqsg3a":{numReplicas:1},"us-west2":null}})`。
   （toml 里的那段保留，作为文档和意图声明。）
2. **`railway redeploy` 复用上一次部署的配置快照**，改完环境配置后 redeploy 还是旧区域。
   要 `railway up` 触发一次新部署才会读新配置。
3. **`railway scale` 在 CLI 4.30.3 里直接 panic**（`Cannot query field "railwayMetal"`），不能用来换区。
   Railway GraphQL 要带 `User-Agent` 头，否则 403。

**核实区域的正确方法**：`railway status --json` →
`latestDeployment.meta.serviceManifest.deploy.multiRegionConfig`。
看的是**最新那次部署**的清单，不是 project 默认区域，也不是 toml。

**教训**：
- **报错说「数据库争用」时，先问是谁占着锁、为什么占这么久**，而不是默认是对方的问题。
  `pg_stat_activity` 里 `state='active', wait_event='ClientRead'` 且 `xact_start` 很老 =
  应用端拿着事务在干别的，这几乎总是延迟或应用逻辑问题。
- **部署后核实实际区域**，不要信 project 默认值或自己写的文档。
- 服务端和数据库永远同区；跨区的代价会被「每事务几百条语句」放大几百倍。

## G-014：笔记没变、图后来才上传 → 永远不会重推

**现象**：全量入库后跑了一遍 `bin/weekly-sync`，slim 新处理了 18 张图，upload 新传了 16 张，
但 ingest 显示「待处理 0」。

**原因**：ingest 只按**笔记源文件**的 sha256 判断要不要重推。
笔记入库时它引用的图如果还没上传，只能保留相对路径（死链）；之后图补传上来了，
笔记文件本身没变，于是永远不会被重推，brain 里一直是死链。
周更场景里这是常态：grokbot 往 vault 同步，图和笔记不一定同一批到。

**修复**：`notes.pushed_sha256` 记录**实际推进 brain 的 markdown**（图片链接重写后）的 sha256。
每次 ingest 先把全部笔记渲染一遍（1,249 篇约一两秒），渲染结果变了才推。
这样一次覆盖三种情况：笔记改了、引用的图补传了、渲染逻辑（notes.py）改了。

**附带修正**：写入超时后回读 `get_page` 只能证明**页面存在**，不能证明是**这一版**落了库
（重推已有页面时这个检查恒为真）。所以回读确认的情况不写 `pushed_sha256`，下次自动重推，
代价只是一次幂等写入。

**迁移**：旧库补列后 `pushed_sha256` 为空 → 第一次运行全量重推。2026-09-22 实测
1,249 篇 17 分钟重推完、失败 0，同时验证了 brain 内容与当前管线完全一致。

**教训**：缓存/跳过的 key 必须覆盖**产出物的全部输入**，而不只是最显眼的那一个。
这里的输入是「笔记 + 图片 URL 映射 + 渲染代码」，只取第一个就会漏。
