"""Import local task state JSON files into PostgreSQL."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from database import get_database_url
from db_task_repository import upsert_import_task, upsert_report_task
from upload_service import normalize_import_stored_path


REPORT_TASKS_PATH = Path("report_tasks.json")
IMPORT_TASKS_PATH = Path("import_tasks.json")


def _load_task_map(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def seed_tasks() -> dict[str, int]:
    """Insert local report/import task snapshots into PostgreSQL."""
    database_url = get_database_url()
    if not database_url:
        raise RuntimeError("DATABASE_URL 未配置，无法导入任务数据")

    report_tasks = _load_task_map(REPORT_TASKS_PATH)
    import_tasks = _load_task_map(IMPORT_TASKS_PATH)

    report_count = 0
    import_count = 0

    for task in report_tasks.values():
        if not isinstance(task, dict):
            continue
        payload = {
            "task_id": str(task.get("task_id", "")).strip(),
            "user_id": str(task.get("user_id", "")).strip(),
            "owner": str(task.get("owner", "")).strip(),
            "status": str(task.get("status", "")).strip(),
            "message": str(task.get("message", "")).strip(),
            "send_email": bool(task.get("send_email", True)),
            "result": task.get("result"),
            "error": str(task.get("error", "")).strip(),
        }
        if not payload["task_id"] or not payload["user_id"]:
            continue
        upsert_report_task(payload)
        report_count += 1

    for task in import_tasks.values():
        if not isinstance(task, dict):
            continue
        payload = {
            "task_id": str(task.get("task_id", "")).strip(),
            "user_id": str(task.get("user_id", "")).strip(),
            "original_file_name": str(task.get("original_file_name", "")).strip(),
            "stored_file_name": str(task.get("stored_file_name", "")).strip(),
            "stored_path": normalize_import_stored_path(
                str(task.get("stored_path", "")).strip(),
                str(task.get("stored_file_name", "")).strip(),
            ),
            "status": str(task.get("status", "")).strip(),
            "message": str(task.get("message", "")).strip(),
            "recognized_positions": task.get("recognized_positions") or [],
            "created_count": int(task.get("created_count", 0) or 0),
            "updated_count": int(task.get("updated_count", 0) or 0),
            "imported_count": int(task.get("imported_count", 0) or 0),
            "error": str(task.get("error", "")).strip(),
        }
        if not payload["task_id"] or not payload["user_id"]:
            continue
        upsert_import_task(payload)
        import_count += 1

    return {
        "report_tasks": report_count,
        "import_tasks": import_count,
    }


if __name__ == "__main__":
    result = seed_tasks()
    print(f"seeded_report_tasks={result['report_tasks']}")
    print(f"seeded_import_tasks={result['import_tasks']}")
