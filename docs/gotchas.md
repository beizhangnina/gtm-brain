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
