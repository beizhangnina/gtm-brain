# gtm-brain — Railway 部署用
#
# 升级 gbrain 只改 GBRAIN_SHA 这一行。
# 当前: garrytan/gbrain @ d13aa74 (release v0.51.0.0, 2026-09-17)

FROM oven/bun:1.3-alpine

RUN apk add --no-cache git ca-certificates curl

# 钉死版本 —— 不要用 master，浮动版本会在某次重部署时无声换掉 schema
ARG GBRAIN_SHA=d13aa742fd68b71bfd6c98be3dda5813791f1d6c

WORKDIR /app

RUN git clone https://github.com/garrytan/gbrain.git . \
 && git checkout ${GBRAIN_SHA} \
 && bun install --frozen-lockfile

# 容器内 gbrain home（config + 运行时状态）
# 无持久卷 —— brain 数据全在 Postgres。重启后 admin token 会重新生成，
# 这是 by design：长期 client 已经 register 在 db 里了。
ENV GBRAIN_HOME=/data
RUN mkdir -p /data && chmod 700 /data

COPY deploy/bin/serve-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 3131

# 故意不加 Dockerfile HEALTHCHECK —— Railway 用 railway.toml 的 healthcheckPath，
# 双重 healthcheck 在冷启动时会互相打架。
ENTRYPOINT ["/entrypoint.sh"]
