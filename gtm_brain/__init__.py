"""gtm-brain — Obsidian GTM vault → 带图的托管 gbrain MCP。

设计不变式：
  * vault 是只读的真源。本包从不写 vault。
  * vault 存原图（Obsidian 体验），云端存瘦身衍生品（agent 体验）。
  * 全流程幂等对账 —— 跑一百遍结果一样，中断随时重跑。
"""

__version__ = "0.1.0"
