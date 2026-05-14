"""Normalize import task stored_path values into stable local/supabase URIs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from db_task_repository import is_db_task_repository_available, upsert_import_task
from upload_service import IMPORT_TASKS_PATH, normalize_import_stored_path


def _load_task_map(path: Path = IMPORT_TASKS_PATH) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _save_task_map(task_map: dict[str, dict[str, Any]], path: Path = IMPORT_TASKS_PATH) -> None:
    path.write_text(
        json.dumps(task_map, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def normalize_import_task_paths() -> dict[str, int]:
    """Normalize stored_path values in local JSON and PostgreSQL import tasks."""
    task_map = _load_task_map()
    updated_count = 0

    for task_id, task in task_map.items():
        if not isinstance(task, dict):
            continue
        old_path = str(task.get("stored_path", "")).strip()
        new_path = normalize_import_stored_path(
            old_path,
            str(task.get("stored_file_name", "")).strip(),
        )
        if new_path == old_path:
            continue
        task["stored_path"] = new_path
        if new_path.startswith("local://uploads/"):
            task["storage_backend"] = "local"
        elif new_path.startswith("supabase://"):
            task["storage_backend"] = "supabase"
        updated_count += 1

        if is_db_task_repository_available():
            payload = {
                "task_id": str(task.get("task_id", task_id)).strip(),
                "user_id": str(task.get("user_id", "")).strip(),
                "original_file_name": str(task.get("original_file_name", "")).strip(),
                "stored_file_name": str(task.get("stored_file_name", "")).strip(),
                "stored_path": str(task.get("stored_path", "")).strip(),
                "status": str(task.get("status", "")).strip(),
                "message": str(task.get("message", "")).strip(),
                "recognized_positions": task.get("recognized_positions") or [],
                "created_count": int(task.get("created_count", 0) or 0),
                "updated_count": int(task.get("updated_count", 0) or 0),
                "imported_count": int(task.get("imported_count", 0) or 0),
                "error": str(task.get("error", "")).strip(),
            }
            if payload["task_id"] and payload["user_id"]:
                upsert_import_task(payload)

    _save_task_map(task_map)
    return {"normalized_import_tasks": updated_count}


if __name__ == "__main__":
    result = normalize_import_task_paths()
    print(f"normalized_import_tasks={result['normalized_import_tasks']}")
