"""Image upload helpers for position import tasks."""

from __future__ import annotations

import json
from pathlib import Path
import time

from database import is_data_backend_strict
from db_task_repository import (
    is_db_task_repository_available,
    load_import_task,
    upsert_import_task,
)
from storage_service import is_storage_backend_strict, upload_bytes_to_uploads_storage


UPLOADS_DIR = Path("uploads")
IMPORT_TASKS_PATH = Path("import_tasks.json")
IMPORT_TASKS: dict[str, dict] = {}
LOCAL_UPLOAD_PREFIX = "local://uploads/"


def _build_local_upload_stored_path(stored_name: str) -> str:
    return f"{LOCAL_UPLOAD_PREFIX}{stored_name}"


def normalize_import_stored_path(stored_path: str, stored_file_name: str = "") -> str:
    """Normalize one import task stored_path into a stable local/supabase URI."""
    value = str(stored_path or "").strip()
    if not value:
        if stored_file_name:
            return _build_local_upload_stored_path(stored_file_name)
        return ""

    if value.startswith("supabase://") or value.startswith(LOCAL_UPLOAD_PREFIX):
        return value

    candidate = Path(value)
    if candidate.name:
        return _build_local_upload_stored_path(candidate.name)

    if stored_file_name:
        return _build_local_upload_stored_path(stored_file_name)
    return value


def _normalize_import_task(task: dict) -> dict:
    normalized = dict(task)
    normalized["stored_path"] = normalize_import_stored_path(
        normalized.get("stored_path", ""),
        normalized.get("stored_file_name", ""),
    )
    if normalized.get("stored_path", "").startswith(LOCAL_UPLOAD_PREFIX):
        normalized["storage_backend"] = "local"
    elif normalized.get("stored_path", "").startswith("supabase://"):
        normalized["storage_backend"] = "supabase"
    return normalized


def _load_import_tasks() -> dict[str, dict]:
    if not IMPORT_TASKS_PATH.exists():
        return {}
    try:
        data = json.loads(IMPORT_TASKS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        task_id: _normalize_import_task(task)
        for task_id, task in data.items()
        if isinstance(task, dict)
    }


def _save_import_tasks() -> None:
    IMPORT_TASKS_PATH.write_text(
        json.dumps(IMPORT_TASKS, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _save_upload_locally(stored_name: str, content: bytes) -> str:
    UPLOADS_DIR.mkdir(exist_ok=True)
    stored_path = UPLOADS_DIR / stored_name
    stored_path.write_bytes(content)
    return _build_local_upload_stored_path(stored_name)


def create_import_task(
    user_id: str,
    filename: str,
    content: bytes,
    content_type: str = "application/octet-stream",
) -> dict:
    """Persist one uploaded screenshot and return the task snapshot."""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    suffix = Path(filename).suffix or ".png"
    task_id = f"import_{user_id}_{timestamp}"
    stored_name = f"{task_id}{suffix}"
    try:
        storage_result = upload_bytes_to_uploads_storage(
            file_name=stored_name,
            content=content,
            content_type=content_type,
        )
        stored_path = storage_result["stored_path"]
        storage_backend = storage_result["backend"]
    except Exception:
        if is_storage_backend_strict():
            raise
        stored_path = _save_upload_locally(stored_name, content)
        storage_backend = "local"

    task = _normalize_import_task(
        {
            "task_id": task_id,
            "user_id": user_id,
            "original_file_name": filename,
            "stored_file_name": stored_name,
            "stored_path": stored_path,
            "storage_backend": storage_backend,
            "status": "uploaded",
            "message": "截图上传成功，等待识别",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
    )
    IMPORT_TASKS[task_id] = task
    if is_db_task_repository_available():
        try:
            persisted = upsert_import_task(task)
            normalized = _normalize_import_task(persisted)
            IMPORT_TASKS[task_id] = normalized
            return normalized
        except Exception:
            if is_data_backend_strict():
                raise
    _save_import_tasks()
    return task


def get_import_task(task_id: str) -> dict | None:
    """Get one import task snapshot."""
    if is_db_task_repository_available():
        try:
            task = load_import_task(task_id)
            if task is not None:
                normalized = _normalize_import_task(task)
                IMPORT_TASKS[task_id] = normalized
                return normalized
        except Exception:
            if is_data_backend_strict():
                raise
    task = IMPORT_TASKS.get(task_id)
    return _normalize_import_task(task) if task else None


IMPORT_TASKS.update(_load_import_tasks())


def update_import_task(task_id: str, **changes) -> dict | None:
    """Update one import task snapshot and persist it."""
    task = IMPORT_TASKS.get(task_id)
    if task is None:
        task = get_import_task(task_id)
        if task is None:
            return None
    task.update(changes)
    task["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    task = _normalize_import_task(task)
    if is_db_task_repository_available():
        try:
            persisted = upsert_import_task(task)
            normalized = _normalize_import_task(persisted)
            IMPORT_TASKS[task_id] = normalized
            return normalized
        except Exception:
            if is_data_backend_strict():
                raise
    IMPORT_TASKS[task_id] = task
    _save_import_tasks()
    return task
