"""把衍生品传到 Supabase Storage。

路径是内容寻址的 `<sha[:2]>/<sha>.<ext>`：
  * 不可枚举 —— 付费 newsletter 的配图不会变成可被发现的公开镜像
  * 天然去重 —— 同一张图出现在多篇文章里只存一份
  * 可设 immutable 缓存 —— 内容变了 hash 就变，URL 跟着变，不存在陈旧缓存
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

# 内容寻址 = URL 永远指向同一份字节，可以放心长缓存
IMMUTABLE_CACHE = "public, max-age=31536000, immutable"


class StorageError(RuntimeError):
    pass


@dataclass
class Storage:
    base_url: str          # https://<ref>.supabase.co
    service_key: str
    bucket: str

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.service_key}",
            "apikey": self.service_key,
        }

    def public_url(self, key: str) -> str:
        return f"{self.base_url}/storage/v1/object/public/{self.bucket}/{key}"

    def ensure_bucket(self, client: httpx.Client) -> str:
        """建 bucket（public read）。已存在就跳过 —— 幂等。"""
        r = client.get(f"{self.base_url}/storage/v1/bucket/{self.bucket}",
                       headers=self._headers)
        if r.status_code == 200:
            info = r.json()
            if not info.get("public"):
                raise StorageError(
                    f"bucket '{self.bucket}' 不是 public。agent 需要能直接 fetch 图片 URL，"
                    f"签名 URL 带不了 header 会失效。请在 Supabase 后台把它设为 public。"
                )
            return "已存在"
        if r.status_code not in (400, 404):
            raise StorageError(f"查 bucket 失败 {r.status_code}: {r.text[:200]}")

        r = client.post(
            f"{self.base_url}/storage/v1/bucket",
            headers=self._headers,
            json={"id": self.bucket, "name": self.bucket, "public": True},
        )
        if r.status_code not in (200, 201):
            raise StorageError(f"建 bucket 失败 {r.status_code}: {r.text[:200]}")
        return "已创建"

    def exists(self, client: httpx.Client, key: str) -> bool:
        r = client.head(self.public_url(key))
        return r.status_code == 200

    def upload(
        self,
        client: httpx.Client,
        key: str,
        data: bytes,
        content_type: str,
    ) -> str:
        r = client.post(
            f"{self.base_url}/storage/v1/object/{self.bucket}/{key}",
            headers={
                **self._headers,
                "Content-Type": content_type,
                "Cache-Control": IMMUTABLE_CACHE,
                # 内容寻址下同 key 必然同字节，重传是无害的
                "x-upsert": "true",
            },
            content=data,
        )
        if r.status_code not in (200, 201):
            raise StorageError(f"上传 {key} 失败 {r.status_code}: {r.text[:200]}")
        return self.public_url(key)


def from_config(cfg) -> Storage:
    if not cfg.supabase_url or not cfg.supabase_service_key:
        raise SystemExit(
            "缺 SUPABASE_URL / SUPABASE_SERVICE_KEY。\n"
            "填进 /Users/beizhang/Documents/AI_Dev/gtm-brain/.env 即可（该文件已被 gitignore）。"
        )
    return Storage(cfg.supabase_url, cfg.supabase_service_key, cfg.supabase_bucket)
