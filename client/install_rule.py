"""把 GTM Brain 规则写进全局指令文件：已有就整段替换，没有就追加。不碰文件里的其他内容。

用法：install_rule.py <规则文件> [目标文件，默认 ~/.claude/CLAUDE.md；Codex 用 ~/.codex/AGENTS.md]
"""
import re, sys
from pathlib import Path
rule = Path(sys.argv[1]).read_text().strip()
target = Path(sys.argv[2]).expanduser() if len(sys.argv) > 2 else Path.home() / ".claude" / "CLAUDE.md"
target.parent.mkdir(parents=True, exist_ok=True)
text = target.read_text() if target.exists() else ""
pattern = re.compile(r"<!-- gtm-brain:start.*?<!-- gtm-brain:end -->", re.S)
new = pattern.sub(lambda _: rule, text) if pattern.search(text) else (text.rstrip() + "\n\n" + rule + "\n").lstrip()
target.write_text(new)
print(f"✓ 规则已写入 {target}（以后问 GTM 问题不用再提 gtm-brain）")
