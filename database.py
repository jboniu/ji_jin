"""Database configuration and connectivity helpers."""

from __future__ import annotations

import importlib
import os
from typing import Any

from dotenv import load_dotenv


def _read_env_flag(name: str, default: bool = False) -> bool:
    load_dotenv()
    value = os.getenv(name, "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def get_database_url() -> str:
    """Return DATABASE_URL from environment, or an empty string."""
    load_dotenv()
    return os.getenv("DATABASE_URL", "").strip()


def is_database_configured() -> bool:
    """Return whether DATABASE_URL is configured."""
    return bool(get_database_url())


def get_data_backend_mode() -> str:
    """Return the current data backend label."""
    return "postgres" if is_database_configured() else "json"


def is_data_backend_strict() -> bool:
    """Return whether production mode should forbid JSON fallback."""
    return _read_env_flag("DATA_BACKEND_STRICT", default=False)


def _load_psycopg_module():
    """Import psycopg lazily so local JSON mode keeps working without it."""
    try:
        return importlib.import_module("psycopg")
    except ImportError:
        return None


def get_database_health() -> dict[str, Any]:
    """Return lightweight database health information for diagnostics."""
    database_url = get_database_url()
    strict_mode = is_data_backend_strict()
    if not database_url:
        return {
            "mode": "json",
            "configured": False,
            "driver": "none",
            "status": "not_configured",
            "strict_mode": strict_mode,
            "message": "DATABASE_URL 未配置，当前仍使用本地 JSON 文件模式",
        }

    psycopg = _load_psycopg_module()
    if psycopg is None:
        return {
            "mode": "postgres",
            "configured": True,
            "driver": "missing",
            "status": "driver_missing",
            "strict_mode": strict_mode,
            "message": "已配置 DATABASE_URL，但未安装 psycopg",
        }

    try:
        with psycopg.connect(database_url, connect_timeout=3) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        return {
            "mode": "postgres",
            "configured": True,
            "driver": "psycopg",
            "status": "ok",
            "strict_mode": strict_mode,
            "message": "数据库连接正常",
        }
    except Exception as exc:  # pragma: no cover - runtime diagnostic path
        return {
            "mode": "postgres",
            "configured": True,
            "driver": "psycopg",
            "status": "error",
            "strict_mode": strict_mode,
            "message": f"数据库连接失败：{exc}",
        }
