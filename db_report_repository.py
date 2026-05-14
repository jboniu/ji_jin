"""Database-backed report index helpers."""

from __future__ import annotations

from typing import Any

from database import get_database_url, is_database_configured


def _connect():
    from psycopg import connect

    return connect(get_database_url(), connect_timeout=3)


def is_db_report_repository_available() -> bool:
    """Return whether database-backed report index reads/writes can be attempted."""
    return is_database_configured()


def upsert_report_index_item(item: dict[str, Any]) -> dict[str, Any]:
    """Insert or update one report index item in PostgreSQL."""
    query = """
        INSERT INTO report_index_items (
            report_id, user_id, owner, file_name, file_type, path, updated_at, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
        ON CONFLICT (report_id) DO UPDATE SET
            user_id = EXCLUDED.user_id,
            owner = EXCLUDED.owner,
            file_name = EXCLUDED.file_name,
            file_type = EXCLUDED.file_type,
            path = EXCLUDED.path,
            updated_at = NOW()
        RETURNING report_id, user_id, owner, file_name, file_type, path, updated_at
    """
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                (
                    str(item.get("report_id", "")).strip(),
                    str(item.get("user_id", "")).strip(),
                    str(item.get("owner", "")).strip(),
                    str(item.get("file_name", "")).strip(),
                    str(item.get("file_type", "")).strip(),
                    str(item.get("path", "")).strip(),
                ),
            )
            row = cursor.fetchone()
        connection.commit()
    return {
        "report_id": row[0],
        "user_id": row[1],
        "owner": row[2],
        "file_name": row[3],
        "file_type": row[4],
        "path": row[5],
        "updated_at": row[6].timestamp() if row[6] else 0,
    }


def load_report_index_items_for_user(user_id: str) -> list[dict[str, Any]]:
    """Load all indexed report items for one user."""
    query = """
        SELECT report_id, user_id, owner, file_name, file_type, path, updated_at
        FROM report_index_items
        WHERE user_id = %s
        ORDER BY updated_at DESC, id DESC
    """
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (user_id,))
            rows = cursor.fetchall()

    return [
        {
            "report_id": row[0],
            "user_id": row[1],
            "owner": row[2],
            "file_name": row[3],
            "file_type": row[4],
            "path": row[5],
            "updated_at": row[6].timestamp() if row[6] else 0,
        }
        for row in rows
    ]
