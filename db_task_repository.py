"""Database-backed task repository helpers."""

from __future__ import annotations

import json
from typing import Any

from database import get_database_url, is_database_configured


def _connect():
    from psycopg import connect

    return connect(get_database_url(), connect_timeout=3)


def is_db_task_repository_available() -> bool:
    """Return whether database-backed task reads/writes can be attempted."""
    return is_database_configured()


def _normalize_report_task_row(row: tuple) -> dict[str, Any]:
    return {
        "task_id": row[0],
        "user_id": row[1],
        "owner": row[2],
        "status": row[3],
        "message": row[4],
        "send_email": bool(row[5]),
        "result": row[6],
        "error": row[7] or "",
        "created_at": row[8].strftime("%Y-%m-%d %H:%M:%S") if row[8] else "",
        "updated_at": row[9].strftime("%Y-%m-%d %H:%M:%S") if row[9] else "",
    }


def _normalize_import_task_row(row: tuple) -> dict[str, Any]:
    stored_path = row[4] or ""
    if str(stored_path).startswith("supabase://"):
        storage_backend = "supabase"
    elif str(stored_path).startswith("local://"):
        storage_backend = "local"
    else:
        storage_backend = ""
    return {
        "task_id": row[0],
        "user_id": row[1],
        "original_file_name": row[2] or "",
        "stored_file_name": row[3] or "",
        "stored_path": stored_path,
        "storage_backend": storage_backend,
        "status": row[5],
        "message": row[6] or "",
        "recognized_positions": row[7] if isinstance(row[7], list) else [],
        "created_count": int(row[8] or 0),
        "updated_count": int(row[9] or 0),
        "imported_count": int(row[10] or 0),
        "error": row[11] or "",
        "created_at": row[12].strftime("%Y-%m-%d %H:%M:%S") if row[12] else "",
        "updated_at": row[13].strftime("%Y-%m-%d %H:%M:%S") if row[13] else "",
    }


def upsert_report_task(task: dict[str, Any]) -> dict[str, Any]:
    """Insert or update one report task in PostgreSQL."""
    query = """
        INSERT INTO report_tasks (
            task_id, user_id, owner, status, message, send_email, result_json, error, created_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, NOW(), NOW())
        ON CONFLICT (task_id) DO UPDATE SET
            user_id = EXCLUDED.user_id,
            owner = EXCLUDED.owner,
            status = EXCLUDED.status,
            message = EXCLUDED.message,
            send_email = EXCLUDED.send_email,
            result_json = EXCLUDED.result_json,
            error = EXCLUDED.error,
            updated_at = NOW()
        RETURNING task_id, user_id, owner, status, message, send_email, result_json, error, created_at, updated_at
    """
    result_json = json.dumps(task.get("result"), ensure_ascii=False) if task.get("result") is not None else None
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                (
                    str(task.get("task_id", "")).strip(),
                    str(task.get("user_id", "")).strip(),
                    str(task.get("owner", "")).strip(),
                    str(task.get("status", "")).strip(),
                    str(task.get("message", "")).strip(),
                    bool(task.get("send_email", True)),
                    result_json,
                    str(task.get("error", "")).strip(),
                ),
            )
            row = cursor.fetchone()
        connection.commit()
    return _normalize_report_task_row(row)


def load_report_task(task_id: str) -> dict[str, Any] | None:
    """Load one report task from PostgreSQL."""
    query = """
        SELECT task_id, user_id, owner, status, message, send_email, result_json, error, created_at, updated_at
        FROM report_tasks
        WHERE task_id = %s
    """
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (task_id,))
            row = cursor.fetchone()
    if row is None:
        return None
    return _normalize_report_task_row(row)


def upsert_import_task(task: dict[str, Any]) -> dict[str, Any]:
    """Insert or update one import task in PostgreSQL."""
    query = """
        INSERT INTO import_tasks (
            task_id, user_id, original_file_name, stored_file_name, stored_path, status, message,
            recognized_positions_json, created_count, updated_count, imported_count, error, created_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, NOW(), NOW())
        ON CONFLICT (task_id) DO UPDATE SET
            user_id = EXCLUDED.user_id,
            original_file_name = EXCLUDED.original_file_name,
            stored_file_name = EXCLUDED.stored_file_name,
            stored_path = EXCLUDED.stored_path,
            status = EXCLUDED.status,
            message = EXCLUDED.message,
            recognized_positions_json = EXCLUDED.recognized_positions_json,
            created_count = EXCLUDED.created_count,
            updated_count = EXCLUDED.updated_count,
            imported_count = EXCLUDED.imported_count,
            error = EXCLUDED.error,
            updated_at = NOW()
        RETURNING
            task_id, user_id, original_file_name, stored_file_name, stored_path, status, message,
            recognized_positions_json, created_count, updated_count, imported_count, error, created_at, updated_at
    """
    positions_json = json.dumps(task.get("recognized_positions") or [], ensure_ascii=False)
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                (
                    str(task.get("task_id", "")).strip(),
                    str(task.get("user_id", "")).strip(),
                    str(task.get("original_file_name", "")).strip(),
                    str(task.get("stored_file_name", "")).strip(),
                    str(task.get("stored_path", "")).strip(),
                    str(task.get("status", "")).strip(),
                    str(task.get("message", "")).strip(),
                    positions_json,
                    int(task.get("created_count", 0) or 0),
                    int(task.get("updated_count", 0) or 0),
                    int(task.get("imported_count", 0) or 0),
                    str(task.get("error", "")).strip(),
                ),
            )
            row = cursor.fetchone()
        connection.commit()
    return _normalize_import_task_row(row)


def load_import_task(task_id: str) -> dict[str, Any] | None:
    """Load one import task from PostgreSQL."""
    query = """
        SELECT
            task_id, user_id, original_file_name, stored_file_name, stored_path, status, message,
            recognized_positions_json, created_count, updated_count, imported_count, error, created_at, updated_at
        FROM import_tasks
        WHERE task_id = %s
    """
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (task_id,))
            row = cursor.fetchone()
    if row is None:
        return None
    return _normalize_import_task_row(row)
