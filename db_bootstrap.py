"""Bootstrap PostgreSQL schema from the local SQL file."""

from __future__ import annotations

from pathlib import Path

from database import get_database_url


SCHEMA_PATH = Path("db_schema.sql")


def apply_schema() -> None:
    """Apply the SQL schema file to the configured database."""
    database_url = get_database_url()
    if not database_url:
        raise RuntimeError("DATABASE_URL 未配置，无法初始化数据库")

    from psycopg import connect

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with connect(database_url, connect_timeout=5) as connection:
        with connection.cursor() as cursor:
            cursor.execute(schema_sql)
        connection.commit()


if __name__ == "__main__":
    apply_schema()
    print("db_schema_applied")
