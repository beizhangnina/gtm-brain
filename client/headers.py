#!/usr/bin/env python3
"""GTM Brain 的 Claude Code headersHelper。

Claude Code 每次连接 MCP 时运行它，把 stdout 当请求头：
    {"Authorization": "Bearer <access token>"}

用 client_credentials 换 token，缓存在同目录的 token.json，过期前 5 分钟续签。
这样凭证配一次就永远不用管 —— 不像写死的 Bearer token 一小时就过期。

只用标准库：同事机器上有 python3 就能跑，不用装任何东西。
Claude Code 给 helper 的时限是 10 秒，所以每个网络请求 4 秒超时。
"""
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / "token.json"


def load_env() -> dict[str, str]:
    env = {}
    for line in (HERE / ".env").read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"')
    return env


def fetch_token(env: dict[str, str]) -> tuple[str, float]:
    base = env["GTM_BRAIN_URL"].rstrip("/")
    # 从发现文档拿 token 端点，不写死路径（gbrain 用 /token，不是常见的 /oauth/token）
    with urllib.request.urlopen(f"{base}/.well-known/oauth-authorization-server", timeout=4) as r:
        endpoint = json.load(r)["token_endpoint"]
    body = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": env["GTM_BRAIN_CLIENT_ID"],
        "client_secret": env["GTM_BRAIN_CLIENT_SECRET"],
        "scope": "read",
    }).encode()
    req = urllib.request.Request(
        endpoint, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=4) as r:
        d = json.load(r)
    return d["access_token"], time.time() + int(d.get("expires_in", 3600))


def main() -> None:
    try:
        cached = json.loads(CACHE.read_text())
        if cached["expires_at"] - 300 < time.time():
            raise ValueError("expiring")
        token = cached["access_token"]
    except (OSError, ValueError, KeyError):
        token, expires_at = fetch_token(load_env())
        CACHE.write_text(json.dumps({"access_token": token, "expires_at": expires_at}))
        os.chmod(CACHE, 0o600)
    print(json.dumps({"Authorization": f"Bearer {token}"}))


if __name__ == "__main__":
    main()
