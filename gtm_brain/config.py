"""从 .env + 环境变量读配置。没有额外依赖，手写解析。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path | None = None) -> None:
    """把 .env 读进 os.environ。已存在的真实环境变量优先，不覆盖。"""
    path = path or REPO_ROOT / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class Config:
    vault_path: Path
    state_db: Path
    voyage_api_key: str | None
    supabase_url: str | None
    supabase_service_key: str | None
    supabase_bucket: str
    brain_url: str | None
    brain_client_id: str | None
    brain_client_secret: str | None

    @classmethod
    def load(cls) -> Config:
        load_dotenv()
        vault = os.environ.get(
            "GTM_VAULT_PATH",
            "/Users/beizhang/Documents/Bei_Brain/01-Projects/Dormy/GTM",
        )
        return cls(
            vault_path=Path(vault).expanduser(),
            state_db=REPO_ROOT / "state.db",
            voyage_api_key=os.environ.get("VOYAGE_API_KEY") or None,
            supabase_url=(os.environ.get("SUPABASE_URL") or "").rstrip("/") or None,
            supabase_service_key=os.environ.get("SUPABASE_SERVICE_KEY") or None,
            supabase_bucket=os.environ.get("SUPABASE_BUCKET", "gtm-assets"),
            brain_url=(os.environ.get("GTM_BRAIN_URL") or "").rstrip("/") or None,
            brain_client_id=os.environ.get("GTM_BRAIN_CLIENT_ID") or None,
            brain_client_secret=os.environ.get("GTM_BRAIN_CLIENT_SECRET") or None,
        )

    def require_vault(self) -> Path:
        if not self.vault_path.is_dir():
            raise SystemExit(f"vault 不存在: {self.vault_path}\n检查 .env 里的 GTM_VAULT_PATH")
        return self.vault_path
