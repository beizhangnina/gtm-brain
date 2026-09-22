#!/usr/bin/env python3
"""把 GTM Brain 的远程 HTTP MCP 桥接成本地 stdio MCP。

给没有 headersHelper 的客户端用（Codex、Cursor、Claude Desktop …）：
它们只能给远程 MCP 填固定 token，而 gbrain 的 token 一小时就过期。
这个桥接每次请求都用 headers.py 的缓存 token（快过期自动续签），
客户端那边只需要配置「运行这个脚本」。

协议：stdin 每行一条 JSON-RPC → POST 到 /mcp → 响应（JSON 或 SSE）逐条写回 stdout。
服务端重启会让 MCP 会话失效（404），这里会自动重放 initialize 再重试，客户端无感。
只用标准库。
"""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import headers  # noqa: E402  同目录的 headers.py

ENV = headers.load_env()
MCP_URL = ENV["GTM_BRAIN_URL"].rstrip("/") + "/mcp"

session_id: str | None = None
init_request: dict | None = None  # 记住客户端的 initialize，会话失效时重放


def auth_header(force_refresh: bool = False) -> str:
    if force_refresh:
        headers.CACHE.unlink(missing_ok=True)
    try:
        cached = json.loads(headers.CACHE.read_text())
        if cached["expires_at"] - 300 < headers.time.time():
            raise ValueError
        return f"Bearer {cached['access_token']}"
    except (OSError, ValueError, KeyError):
        token, expires_at = headers.fetch_token(ENV)
        headers.CACHE.write_text(json.dumps({"access_token": token, "expires_at": expires_at}))
        headers.os.chmod(headers.CACHE, 0o600)
        return f"Bearer {token}"


def post(msg: dict, force_refresh: bool = False) -> list[dict]:
    """发一条消息，返回服务端回的所有 JSON-RPC 消息（通知类返回空列表）。"""
    global session_id
    hd = {"Authorization": auth_header(force_refresh), "Content-Type": "application/json",
          "Accept": "application/json, text/event-stream"}
    if session_id:
        hd["Mcp-Session-Id"] = session_id
    req = urllib.request.Request(MCP_URL, data=json.dumps(msg).encode(), headers=hd)
    with urllib.request.urlopen(req, timeout=120) as r:
        session_id = r.headers.get("Mcp-Session-Id") or session_id
        body = r.read().decode("utf-8", errors="replace")
    if not body.strip():
        return []
    if "text/event-stream" in (r.headers.get("Content-Type") or ""):
        return [json.loads(line[5:]) for line in body.splitlines()
                if line.startswith("data:") and line[5:].strip()]
    parsed = json.loads(body)
    return parsed if isinstance(parsed, list) else [parsed]


def reinitialize() -> None:
    global session_id
    session_id = None
    if init_request:
        post(init_request)
        post({"jsonrpc": "2.0", "method": "notifications/initialized"})


def handle(msg: dict) -> list[dict]:
    global init_request
    if msg.get("method") == "initialize":
        init_request = msg
    try:
        return post(msg)
    except urllib.error.HTTPError as e:
        if e.code == 401:                      # token 被提前作废：强制续签重试一次
            return post(msg, force_refresh=True)
        if e.code == 404 and session_id and msg.get("method") != "initialize":
            reinitialize()                     # 服务端重启，会话丢了
            return post(msg)
        raise


def main() -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        msg = json.loads(line)
        try:
            replies = handle(msg)
        except Exception as e:  # 出错也要给客户端一个回应，不能让它干等
            if "id" not in msg:
                continue
            replies = [{"jsonrpc": "2.0", "id": msg["id"],
                        "error": {"code": -32000, "message": f"gtm-brain 桥接出错: {e}"[:500]}}]
        for reply in replies:
            sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
