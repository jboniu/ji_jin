"""Storage configuration and connectivity helpers."""

from __future__ import annotations

import os
from pathlib import Path
import re
from typing import Any
import uuid

from dotenv import load_dotenv


def _read_env_flag(name: str, default: bool = False) -> bool:
    load_dotenv()
    value = os.getenv(name, "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def get_supabase_url() -> str:
    """Return SUPABASE_URL from environment, or an empty string."""
    load_dotenv()
    return os.getenv("SUPABASE_URL", "").strip()


def get_supabase_service_role_key() -> str:
    """Return SUPABASE_SERVICE_ROLE_KEY from environment, or an empty string."""
    load_dotenv()
    return os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()


def get_uploads_bucket_name() -> str:
    """Return the configured uploads bucket name."""
    load_dotenv()
    return os.getenv("SUPABASE_STORAGE_BUCKET_UPLOADS", "").strip()


def get_reports_bucket_name() -> str:
    """Return the configured reports bucket name."""
    load_dotenv()
    return os.getenv("SUPABASE_STORAGE_BUCKET_REPORTS", "").strip()


def is_remote_storage_configured() -> bool:
    """Return whether Supabase Storage has enough config to be attempted."""
    return bool(
        get_supabase_url()
        and get_supabase_service_role_key()
        and get_uploads_bucket_name()
        and get_reports_bucket_name()
    )


def get_storage_backend_mode() -> str:
    """Return the current storage backend label."""
    return "supabase" if is_remote_storage_configured() else "local"


def is_storage_backend_strict() -> bool:
    """Return whether production mode should forbid local storage fallback."""
    return _read_env_flag("STORAGE_BACKEND_STRICT", default=False)


def get_storage_health() -> dict[str, Any]:
    """Return lightweight storage health information for diagnostics."""
    strict_mode = is_storage_backend_strict()
    if not is_remote_storage_configured():
        return {
            "mode": "local",
            "configured": False,
            "status": "not_configured",
            "strict_mode": strict_mode,
            "message": "未配置 Supabase Storage，当前仍使用本地文件存储",
            "uploads_bucket": get_uploads_bucket_name() or "",
            "reports_bucket": get_reports_bucket_name() or "",
        }

    try:
        import requests

        url = f"{get_supabase_url().rstrip('/')}/storage/v1/bucket"
        response = requests.get(
            url,
            headers={
                "apikey": get_supabase_service_role_key(),
                "Authorization": f"Bearer {get_supabase_service_role_key()}",
            },
            timeout=5,
        )
        if 200 <= response.status_code < 300:
            return {
                "mode": "supabase",
                "configured": True,
                "status": "ok",
                "strict_mode": strict_mode,
                "message": "对象存储连接正常",
                "uploads_bucket": get_uploads_bucket_name(),
                "reports_bucket": get_reports_bucket_name(),
            }
        return {
            "mode": "supabase",
            "configured": True,
            "status": "error",
            "strict_mode": strict_mode,
            "message": f"对象存储连接失败：HTTP {response.status_code}",
            "uploads_bucket": get_uploads_bucket_name(),
            "reports_bucket": get_reports_bucket_name(),
        }
    except Exception as exc:  # pragma: no cover - runtime diagnostic path
        return {
            "mode": "supabase",
            "configured": True,
            "status": "error",
            "strict_mode": strict_mode,
            "message": f"对象存储连接失败：{exc}",
            "uploads_bucket": get_uploads_bucket_name(),
            "reports_bucket": get_reports_bucket_name(),
        }


def _storage_headers(content_type: str) -> dict[str, str]:
    return {
        "apikey": get_supabase_service_role_key(),
        "Authorization": f"Bearer {get_supabase_service_role_key()}",
        "x-upsert": "true",
        "content-type": content_type or "application/octet-stream",
    }


def _upload_bytes_to_bucket(
    *,
    bucket_name: str,
    object_name: str,
    content: bytes,
    content_type: str,
) -> dict[str, str]:
    """Upload raw bytes to one Supabase Storage bucket."""
    if not is_remote_storage_configured():
        raise RuntimeError("Supabase Storage 未配置")

    import requests

    url = f"{get_supabase_url().rstrip('/')}/storage/v1/object/{bucket_name}/{object_name}"
    response = requests.post(
        url,
        headers=_storage_headers(content_type),
        data=content,
        timeout=15,
    )
    if not 200 <= response.status_code < 300:
        raise RuntimeError(f"Supabase Storage 上传失败：HTTP {response.status_code}")

    return {
        "backend": "supabase",
        "stored_path": f"supabase://{bucket_name}/{object_name}",
        "object_name": object_name,
    }


def _download_bytes_from_bucket(bucket_name: str, object_name: str) -> bytes:
    """Download raw bytes from one Supabase Storage bucket."""
    if not is_remote_storage_configured():
        raise RuntimeError("Supabase Storage 未配置")

    import requests

    url = f"{get_supabase_url().rstrip('/')}/storage/v1/object/{bucket_name}/{object_name}"
    response = requests.get(
        url,
        headers={
            "apikey": get_supabase_service_role_key(),
            "Authorization": f"Bearer {get_supabase_service_role_key()}",
        },
        timeout=15,
    )
    if not 200 <= response.status_code < 300:
        raise RuntimeError(f"Supabase Storage 下载失败：HTTP {response.status_code}")
    return response.content


def upload_bytes_to_uploads_storage(
    file_name: str,
    content: bytes,
    content_type: str = "application/octet-stream",
) -> dict[str, str]:
    """Upload one file to the configured uploads storage bucket."""
    object_name = f"imports/{Path(file_name).name}"
    bucket_name = get_uploads_bucket_name()
    result = _upload_bytes_to_bucket(
        bucket_name=bucket_name,
        object_name=object_name,
        content=content,
        content_type=content_type or "application/octet-stream",
    )
    return {
        **result,
        "stored_file_name": Path(file_name).name,
    }


def upload_bytes_to_reports_storage(
    file_name: str,
    content: bytes,
    content_type: str = "application/msword",
) -> dict[str, str]:
    """Upload one generated report to the configured reports bucket."""
    stem = Path(file_name).stem
    suffix = Path(file_name).suffix or ".doc"
    safe_stem = re.sub(r"[^A-Za-z0-9_-]+", "_", stem).strip("_")
    if not safe_stem:
        safe_stem = f"report_{uuid.uuid4().hex[:12]}"
    object_name = f"reports/{safe_stem}{suffix.lower()}"
    bucket_name = get_reports_bucket_name()
    result = _upload_bytes_to_bucket(
        bucket_name=bucket_name,
        object_name=object_name,
        content=content,
        content_type=content_type or "application/msword",
    )
    return {
        **result,
        "stored_file_name": Path(file_name).name,
    }


def read_text_from_reports_storage(stored_path: str, encoding: str = "utf-8") -> str:
    """Read one report file text from Supabase Storage using a stored_path."""
    prefix = f"supabase://{get_reports_bucket_name()}/"
    if not stored_path.startswith(prefix):
        raise RuntimeError("报告存储路径不是当前 reports bucket")
    object_name = stored_path[len(prefix) :]
    content = _download_bytes_from_bucket(get_reports_bucket_name(), object_name)
    return content.decode(encoding, errors="ignore")
