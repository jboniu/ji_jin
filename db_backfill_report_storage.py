"""Backfill local report files into Supabase Storage and update report index paths."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from db_report_repository import is_db_report_repository_available, upsert_report_index_item
from report_service import REPORT_INDEX_PATH, REPORTS_DIR
from storage_service import upload_bytes_to_reports_storage


def _load_report_index() -> list[dict[str, Any]]:
    if not REPORT_INDEX_PATH.exists():
        return []
    data = json.loads(REPORT_INDEX_PATH.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def _save_report_index(items: list[dict[str, Any]]) -> None:
    REPORT_INDEX_PATH.write_text(
        json.dumps(items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _resolve_local_report_path(item: dict[str, Any]) -> Path | None:
    stored_path = str(item.get("path", "")).strip()
    if stored_path.startswith("supabase://"):
        return None

    if stored_path:
        candidate = Path(stored_path)
        if candidate.exists():
            return candidate

    file_name = str(item.get("file_name") or item.get("report_id") or "").strip()
    if file_name:
        candidate = REPORTS_DIR / file_name
        if candidate.exists():
            return candidate

    return None


def backfill_report_storage() -> dict[str, int]:
    """Upload indexed local reports to Supabase and update their index paths."""
    items = _load_report_index()
    uploaded_count = 0
    skipped_count = 0
    missing_count = 0

    for item in items:
        if not isinstance(item, dict):
            skipped_count += 1
            continue

        if str(item.get("path", "")).strip().startswith("supabase://"):
            skipped_count += 1
            continue

        local_path = _resolve_local_report_path(item)
        if local_path is None:
            missing_count += 1
            continue

        uploaded = upload_bytes_to_reports_storage(
            file_name=local_path.name,
            content=local_path.read_bytes(),
            content_type="application/msword",
        )
        item["path"] = uploaded["stored_path"]
        uploaded_count += 1

        if is_db_report_repository_available():
            payload = {
                "report_id": str(item.get("report_id", "")).strip(),
                "user_id": str(item.get("user_id", "")).strip(),
                "owner": str(item.get("owner", "")).strip(),
                "file_name": str(item.get("file_name", "")).strip(),
                "file_type": str(item.get("file_type", "")).strip(),
                "path": str(item.get("path", "")).strip(),
            }
            if payload["report_id"] and payload["user_id"]:
                upsert_report_index_item(payload)

    _save_report_index(items)
    return {
        "uploaded": uploaded_count,
        "skipped": skipped_count,
        "missing": missing_count,
    }


if __name__ == "__main__":
    result = backfill_report_storage()
    print(f"backfilled_report_storage={result['uploaded']}")
    print(f"skipped_report_storage={result['skipped']}")
    print(f"missing_local_reports={result['missing']}")
