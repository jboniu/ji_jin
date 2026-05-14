"""Helpers for listing and reading generated report files."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

from database import is_data_backend_strict
from db_report_repository import is_db_report_repository_available, load_report_index_items_for_user
from report_service import REPORT_INDEX_PATH, REPORTS_DIR
from storage_service import is_storage_backend_strict, read_text_from_reports_storage
from user_service import get_user_by_id


def _is_visible_report(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in {".md", ".doc"} and path.name != ".gitkeep"


def _build_report_id(path: Path) -> str:
    return path.name


def _resolve_report_path(report_id: str) -> Path:
    return REPORTS_DIR / report_id


def _matches_user(path: Path, owner: str) -> bool:
    return owner in path.stem if owner else False


def _load_report_index() -> list[dict[str, Any]]:
    if not REPORT_INDEX_PATH.exists():
        return []
    try:
        data = json.loads(REPORT_INDEX_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _format_timestamp(value: float) -> str:
    return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S")


def _raise_if_data_backend_strict() -> None:
    if is_data_backend_strict():
        raise


def _raise_if_storage_backend_strict() -> None:
    if is_storage_backend_strict():
        raise


def list_reports_for_user(user_id: str) -> dict[str, Any] | None:
    """List report files that belong to one user based on the owner name in filenames."""
    user = get_user_by_id(user_id)
    if user is None:
        return None

    owner = str(user.get("owner", "")).strip()
    REPORTS_DIR.mkdir(exist_ok=True)
    items: list[dict[str, Any]] = []

    if is_db_report_repository_available():
        try:
            db_items = load_report_index_items_for_user(user_id)
            for item in db_items:
                items.append(
                    {
                        "report_id": item.get("report_id", ""),
                        "file_name": item.get("file_name", ""),
                        "file_type": item.get("file_type", ""),
                        "owner": item.get("owner", owner),
                        "updated_at": item.get("updated_at"),
                        "updated_at_text": _format_timestamp(float(item.get("updated_at", 0) or 0)),
                        "path": item.get("path", ""),
                    }
                )
            if items:
                return {
                    "user_id": user_id,
                    "owner": owner,
                    "items": items,
                    "total": len(items),
                }
        except Exception:
            _raise_if_data_backend_strict()

    indexed_items = _load_report_index()
    for item in indexed_items:
        if str(item.get("user_id", "")).strip() != user_id:
            continue
        items.append(
            {
                "report_id": item.get("report_id", ""),
                "file_name": item.get("file_name", ""),
                "file_type": item.get("file_type", ""),
                "owner": item.get("owner", owner),
                "updated_at": item.get("updated_at"),
                "updated_at_text": _format_timestamp(float(item.get("updated_at", 0) or 0)),
                "path": item.get("path", ""),
            }
        )

    if items:
        return {
            "user_id": user_id,
            "owner": owner,
            "items": items,
            "total": len(items),
        }

    for path in sorted(REPORTS_DIR.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
        if not _is_visible_report(path):
            continue
        if owner and not _matches_user(path, owner):
            continue

        items.append(
            {
                "report_id": _build_report_id(path),
                "file_name": path.name,
                "file_type": path.suffix.lower().lstrip("."),
                "owner": owner,
                "updated_at": path.stat().st_mtime,
                "updated_at_text": _format_timestamp(path.stat().st_mtime),
                "path": str(path.resolve()),
            }
        )

    return {
        "user_id": user_id,
        "owner": owner,
        "items": items,
        "total": len(items),
    }


def get_report_detail_for_user(user_id: str, report_id: str) -> dict[str, Any] | None:
    """Read one report detail if the file belongs to the specified user."""
    reports = list_reports_for_user(user_id)
    if reports is None:
        return None

    matched = next((item for item in reports["items"] if item["report_id"] == report_id), None)
    if matched is None:
        return {}

    path = _resolve_report_path(report_id)
    if path.exists():
        content = path.read_text(encoding="utf-8", errors="ignore")
    else:
        stored_path = str(matched.get("path", "")).strip()
        if not stored_path.startswith("supabase://"):
            return {}
        try:
            content = read_text_from_reports_storage(stored_path)
        except Exception:
            _raise_if_storage_backend_strict()
            return {}

    return {
        **matched,
        "content": content,
    }
