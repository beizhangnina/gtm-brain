#!/bin/sh
# gtm-brain 容器入口：读 env → 写 gbrain config → 启 OAuth MCP server。
#
# 绝不用 `set -x` —— 它会把 secret 的值 trace 进 Railway logs。
# 需要诊断就手动 echo 安全字段（长度、前缀），不 echo 值。

echo "[entrypoint] starting"
echo "[entrypoint] bun=$(command -v bun || echo NOT_FOUND)"

# ============================================================
# 1. 必需 env 校验 —— fail fast，但要响，且不泄密
# ============================================================

fail=0
if [ -z "$GTM_BRAIN_DATABASE_URL" ]; then
  echo "[entrypoint] FATAL: GTM_BRAIN_DATABASE_URL 未设置" >&2; fail=1
fi
if [ -z "$VOYAGE_API_KEY" ]; then
  echo "[entrypoint] FATAL: VOYAGE_API_KEY 未设置（文本+图片 embedding 都要它）" >&2; fail=1
fi
[ "$fail" = "1" ] && exit 1

echo "[entrypoint] env ok (db url len=${#GTM_BRAIN_DATABASE_URL}, voyage key len=${#VOYAGE_API_KEY})"

# 防御：别让环境里飘来的 DATABASE_URL 劫持引擎推断。
# 这是从 dormy-brain 那边继承的教训 —— 在 Railway 上 Postgres 插件会自动注入
# DATABASE_URL，而 gbrain 看到它会走完全不同的连接路径。
unset DATABASE_URL GBRAIN_DATABASE_URL

# Supabase 专属：gbrain 看到 pooler URL 会自动推导出对应的 Direct URL
# (db.<ref>.supabase.co)，而那个是 IPv6-only，DNS 解析经常失败。
# 强制只走 session pooler。这条是 dormy-brain 花了好几轮才定位的。
export GBRAIN_DISABLE_DIRECT_POOL="${GBRAIN_DISABLE_DIRECT_POOL:-1}"

# ============================================================
# 2. gbrain config
# ============================================================

# 配置目录必须是 "$GBRAIN_HOME/.gbrain"（gbrain 强制 append .gbrain）
GBRAIN_DIR="${GBRAIN_HOME:-$HOME}/.gbrain"
mkdir -p "$GBRAIN_DIR"
echo "[entrypoint] GBRAIN_DIR=$GBRAIN_DIR"

# ⚠️ embedding_model / embedding_dimensions 在 initSchema 之前就决定向量列宽。
# 第一次启动配错 = 整库要重建。voyage-4 原生 1024 维。
# embedding_multimodal 默认关闭，必须显式打开才会给图片建向量。
# LLM（think 综合 + query 扩展）走 flatkey 上的 deepseek-v4-flash，只为省钱。
# 借用 gbrain 的 deepseek recipe（它会把 reasoning_content 提到 content），
# 只把 base_url 换成 flatkey；key 放在 DEEPSEEK_API_KEY（flatkey 的 gtm-brain 专用 key）。
# think 选模型：models.think → models.default → GBRAIN_MODEL，所以这里导出 GBRAIN_MODEL。
LLM_MODEL="${GTM_BRAIN_LLM_MODEL:-deepseek:deepseek-v4-flash}"
export GBRAIN_MODEL="$LLM_MODEL"
if [ -z "$DEEPSEEK_API_KEY" ]; then
  echo "[entrypoint] WARN: DEEPSEEK_API_KEY 未设置 —— think 只会返回原文摘录，query 不做扩展" >&2
fi

cat > "$GBRAIN_DIR/config.json" <<JSON
{
  "engine": "postgres",
  "database_url": "${GTM_BRAIN_DATABASE_URL}",
  "embedding_model": "voyage:voyage-4",
  "embedding_dimensions": 1024,
  "embedding_multimodal": true,
  "embedding_multimodal_model": "voyage:voyage-multimodal-3",
  "chat_model": "${LLM_MODEL}",
  "expansion_model": "${LLM_MODEL}",
  "provider_base_urls": { "deepseek": "https://router.flatkey.ai/v1" }
}
JSON
chmod 600 "$GBRAIN_DIR/config.json"
echo "[entrypoint] config written (engine=postgres, embed=voyage:voyage-4@1024, multimodal=on, llm=${LLM_MODEL} via flatkey, key len=${#DEEPSEEK_API_KEY})"

# ============================================================
# 3. Public URL（OAuth issuer 要用）
# ============================================================

if [ -z "$PUBLIC_URL" ] && [ -n "$RAILWAY_PUBLIC_DOMAIN" ]; then
  export PUBLIC_URL="https://${RAILWAY_PUBLIC_DOMAIN}"
fi

# ============================================================
# 4. 启动
# ============================================================

PORT="${PORT:-3131}"
echo "================================================"
echo " gtm-brain HTTP MCP server"
echo " Port:   $PORT"
echo " Public: ${PUBLIC_URL:-<localhost only>}"
echo "================================================"

# --bind 0.0.0.0 是必须的：gbrain v0.34.1 起默认 bind 127.0.0.1，
# 容器里那样绑等于只有自己能连，Railway 的反向代理够不到，
# 外部请求全部被拒（而且 healthcheck 也过不了）。
SERVE_ARGS="--http --port $PORT --bind 0.0.0.0"
[ -n "$PUBLIC_URL" ] && SERVE_ARGS="$SERVE_ARGS --public-url $PUBLIC_URL"

echo "[entrypoint] exec: bun /app/src/cli.ts serve $SERVE_ARGS"

# exec → PID 1 → Railway 能正确处理 signal + restart
exec bun /app/src/cli.ts serve $SERVE_ARGS
