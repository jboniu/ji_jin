"""Update one user's password in PostgreSQL."""

from __future__ import annotations

import sys

from database import get_database_url


def update_password(user_id: str, new_password: str) -> int:
    """Update password_hash for one user_id and return affected row count."""
    database_url = get_database_url()
    if not database_url:
        raise RuntimeError("DATABASE_URL 未配置，无法更新数据库密码")
    if not user_id.strip():
        raise ValueError("user_id 不能为空")
    if not new_password:
        raise ValueError("new_password 不能为空")

    from psycopg import connect

    with connect(database_url, connect_timeout=5) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE app_users
                SET password_hash = %s, updated_at = NOW()
                WHERE user_id = %s
                """,
                (new_password, user_id.strip()),
            )
            affected = cursor.rowcount
        connection.commit()
    return affected


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("用法: python db_update_password.py <user_id> <new_password>")
    count = update_password(sys.argv[1], sys.argv[2])
    print(f"updated_users={count}")
