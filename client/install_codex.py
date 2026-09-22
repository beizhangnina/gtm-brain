"""把 gtm-brain 配进 Codex（~/.codex/config.toml）：已有就整段替换，没有就追加。

Codex 没有 headersHelper，所以配的是本地 stdio 桥接（stdio_bridge.py），由它负责换 token。
python 用安装时的绝对路径 —— ChatGPT App 启动 MCP 时的 PATH 跟终端不一样，写 python3 可能找不到。
"""
import re
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
cfg = Path.home() / ".codex" / "config.toml"
cfg.parent.mkdir(parents=True, exist_ok=True)
block = f'''# gtm-brain:start（由 GTM Brain 安装脚本维护，重装会整段替换）
[mcp_servers.gtm-brain]
command = "{sys.executable}"
args = ["{here / 'stdio_bridge.py'}"]
startup_timeout_sec = 30
# gtm-brain:end'''
text = cfg.read_text() if cfg.exists() else ""
pattern = re.compile(r"# gtm-brain:start.*?# gtm-brain:end", re.S)
if pattern.search(text):
    text = pattern.sub(lambda _: block, text)
elif re.search(r"^\[mcp_servers\.gtm-brain\]", text, re.M):
    sys.exit("✗ config.toml 里已经有一个手写的 [mcp_servers.gtm-brain]，先删掉它再重跑")
else:
    text = text.rstrip() + "\n\n" + block + "\n"
cfg.write_text(text)
print("✓ 已配进 Codex（~/.codex/config.toml）")
