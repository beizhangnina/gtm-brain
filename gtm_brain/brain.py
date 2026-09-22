"""gbrain HTTP MCP 客户端：OAuth client_credentials + put_page。

只做 ingest 需要的最小面，不是通用 MCP 客户端。
"""

from __future__ import annotations

import json
import uuid
import time
from dataclasses import dataclass, field

import httpx


class BrainError(RuntimeError):
    pass


# 这两种都是「重试就好」的瞬时状态，服务端在 suggestion 里明说了要
# 用同一个 request_id 重试（request_id 保证幂等，不会写两遍）。
# 把它们当失败处理，会在并发下损失大批写入 —— 实测 8 并发时 20 篇失败 16 篇。
RETRYABLE_WRITE_ERRORS = {"write_pending", "storage_error"}

# 连接层的瞬时故障。跟上面那组不同，这些不是 gbrain 返回的业务错误，
# 而是 httpx 层直接抛的异常 —— 长跑 ingest 里服务端偶尔会断连
# （实测 450 篇里有 5 篇栽在这上面）。写入由 request_id 保证幂等，
# 重试不会写两遍，所以这里可以放心重试。
TRANSIENT_NETWORK_ERRORS = (
    httpx.RemoteProtocolError,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.ConnectTimeout,
    httpx.ConnectError,
    httpx.ReadError,
    httpx.WriteError,
    httpx.PoolTimeout,
)


@dataclass
class BrainClient:
    base_url: str          # https://xxx.up.railway.app
    client_id: str
    client_secret: str
    _token: str | None = field(default=None, repr=False)
    _expires_at: float = 0.0
    _mcp_session: str | None = field(default=None, repr=False)
    _token_endpoint: str | None = field(default=None, repr=False)

    # ---- auth ---------------------------------------------------

    def _discover_token_endpoint(self, client: httpx.Client) -> str:
        """从 OAuth 发现文档拿 token 端点，不要写死路径。

        实测：gbrain 用的是 `/token`，不是常见的 `/oauth/token`。
        写死会在某次上游改路径时无声失效。
        """
        if self._token_endpoint:
            return self._token_endpoint
        r = client.get(f"{self.base_url}/.well-known/oauth-authorization-server")
        if r.status_code != 200:
            raise BrainError(f"取 OAuth 发现文档失败 {r.status_code}")
        ep = r.json().get("token_endpoint")
        if not ep:
            raise BrainError("发现文档里没有 token_endpoint")
        self._token_endpoint = ep
        return ep

    def token(self, client: httpx.Client) -> str:
        """拿 access token。提前 60s 续签 —— 长跑 ingest 不该在中途 401。"""
        if self._token and time.time() < self._expires_at - 60:
            return self._token
        r = client.post(
            self._discover_token_endpoint(client),
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "read write",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if r.status_code != 200:
            raise BrainError(f"取 token 失败 {r.status_code}: {r.text[:300]}")
        d = r.json()
        self._token = d["access_token"]
        self._expires_at = time.time() + int(d.get("expires_in", 3600))
        return self._token

    # ---- MCP ----------------------------------------------------

    def _headers(self, client: httpx.Client) -> dict[str, str]:
        h = {
            "Authorization": f"Bearer {self.token(client)}",
            "Content-Type": "application/json",
            # Streamable HTTP 传输要求同时接受这两种
            "Accept": "application/json, text/event-stream",
        }
        if self._mcp_session:
            h["Mcp-Session-Id"] = self._mcp_session
        return h

    def initialize(self, client: httpx.Client) -> dict:
        r = client.post(
            f"{self.base_url}/mcp",
            headers=self._headers(client),
            json={
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "gtm-brain-ingest", "version": "0.1.0"},
                },
            },
        )
        if sid := r.headers.get("mcp-session-id"):
            self._mcp_session = sid
        return _parse_mcp(r)

    def call(self, client: httpx.Client, tool: str, args: dict) -> dict:
        r = client.post(
            f"{self.base_url}/mcp",
            headers=self._headers(client),
            json={
                "jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": tool, "arguments": args},
            },
        )
        return _parse_mcp(r)


def _parse_mcp(r: httpx.Response) -> dict:
    """gbrain 的 HTTP 传输可能回 JSON，也可能回 SSE。两种都要能解。"""
    if r.status_code >= 400:
        raise BrainError(f"MCP {r.status_code}: {r.text[:400]}")
    ctype = r.headers.get("content-type", "")
    if "text/event-stream" in ctype:
        for line in r.text.splitlines():
            if line.startswith("data:"):
                payload = json.loads(line[5:].strip())
                if "result" in payload or "error" in payload:
                    return payload
        raise BrainError(f"SSE 里没有 result: {r.text[:300]}")
    return r.json()


def from_config(cfg) -> BrainClient:
    missing = [n for n, v in (
        ("GTM_BRAIN_URL", cfg.brain_url),
        ("GTM_BRAIN_CLIENT_ID", cfg.brain_client_id),
        ("GTM_BRAIN_CLIENT_SECRET", cfg.brain_client_secret),
    ) if not v]
    if missing:
        raise SystemExit(f"缺 {', '.join(missing)} —— brain 部署完再填进 .env")
    return BrainClient(cfg.brain_url, cfg.brain_client_id, cfg.brain_client_secret)


def with_network_retry(fn, *, attempts: int = 6, what: str = "请求"):
    """把瞬时网络故障挡在外面的通用重试。

    教训：最初只在 put_page_sync 内部重试，结果启动阶段的
    token() 一次 ReadTimeout 就把整轮跑了 11 小时的任务崩掉了
    （见 docs/gotchas.md G-012）。凡是走网络的调用都要包一层。
    """
    for i in range(1, attempts + 1):
        try:
            return fn()
        except TRANSIENT_NETWORK_ERRORS as exc:
            if i == attempts:
                raise BrainError(f"{what}连续失败 {attempts} 次: {exc!r}"[:300]) from exc
            time.sleep(min(2 ** i, 30))
    raise BrainError(f"{what}重试耗尽")


def mcp_error(resp: dict) -> str | None:
    """MCP 的错误有两种藏法，都要查。

    1. JSON-RPC 层的 `error`
    2. `result.isError` + content[0].text 里一个 JSON 错误体
       —— gbrain 用的是第 2 种：HTTP 200、jsonrpc 无 error，
       只看 `"error" in resp` 会把失败当成功。
    """
    # 不要在这里截断 —— 调用方要拿它去 json.loads 判断是不是 write_pending，
    # 截断会把 JSON 截坏（踩过）。截断留给最终抛异常时做。
    if "error" in resp:
        return json.dumps(resp["error"], ensure_ascii=False)
    res = resp.get("result")
    if isinstance(res, dict) and res.get("isError"):
        return (res.get("content") or [{}])[0].get("text") or ""
    return None


def _result_text(resp: dict) -> str:
    res = resp.get("result")
    if isinstance(res, dict):
        return ((res.get("content") or [{}])[0].get("text") or "")
    return str(res)


def put_page_sync(
    bc: BrainClient,
    client: httpx.Client,
    slug: str,
    content: str,
    *,
    # 单篇写入固定开销约 40s（Railway 在新加坡，Voyage 在美国，
    # 单次 embedding 往返实测 ~9s），并发下更长。120s 会大批误判超时。
    timeout_s: float = 900.0,
    poll_s: float = 0.6,
) -> dict:
    """同步版 put_page。

    gbrain v0.51 起写入是**异步**的：put_page 先回 `write_pending`，
    带一个 request_id，真正落库在后台。不轮询就直接当成功，
    会得到一堆「写了但其实没写」的假阳性。

    契约（来自 put_page 的 suggestion）：用同一个 request_id 和同样的参数重试，
    直到不再 pending。request_id 让重试是幂等的，不会写两遍。
    """
    request_id = str(uuid.uuid4())
    args = {"slug": slug, "content": content, "force": True, "request_id": request_id}
    deadline = time.time() + timeout_s
    last = ""
    backoff = 1.0
    net_retries = 0
    while time.time() < deadline:
        try:
            resp = bc.call(client, "put_page", args)
        except TRANSIENT_NETWORK_ERRORS as exc:
            net_retries += 1
            if net_retries > 6:
                raise BrainError(f"连接反复失败（{net_retries} 次）: {exc!r}"[:400])
            # 同一个 request_id 重发 —— 服务端可能已经收下了，
            # 幂等保证不会产生第二次写入
            time.sleep(min(2 ** net_retries, 30))
            continue
        err = mcp_error(resp)
        if err is None:
            return resp
        last = err
        try:
            parsed = json.loads(err)
        except Exception:
            raise BrainError(err[:400])
        kind = parsed.get("error")
        if kind not in RETRYABLE_WRITE_ERRORS:
            raise BrainError(err[:400])

        if kind == "storage_error":
            # "Write admission is temporarily blocked by database contention."
            # 是瞬时信号，服务端自己就建议用同一个 request_id 重试。
            # 指数退避让开争用窗口，别硬顶上去。
            time.sleep(backoff)
            backoff = min(backoff * 2, 15.0)
        else:
            # write_pending：服务端会给建议间隔，照它的来
            wait_ms = (parsed.get("write_request") or {}).get("retry_after_ms")
            time.sleep((wait_ms / 1000) if wait_ms else poll_s)
    raise BrainError(f"put_page 超时（{timeout_s}s）仍 pending: {last[:300]}")
