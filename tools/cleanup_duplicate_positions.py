from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from psycopg import connect


ROOT = Path(__file__).resolve().parents[1]
BACKUP_DIR = ROOT / "reports" / "db_cleanup"


def load_database_url() -> str:
    env_path = ROOT / ".env"
    with env_path.open("r", encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if line.startswith("DATABASE_URL="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError("DATABASE_URL not found in .env")


def fetch_duplicate_rows(connection) -> list[tuple]:
    query = """
    SELECT
        p.id,
        u.user_id,
        u.owner,
        COALESCE(NULLIF(TRIM(p.fund_code), ''), '') AS fund_code,
        COALESCE(NULLIF(TRIM(p.fund_name), ''), '') AS fund_name,
        COALESCE(NULLIF(TRIM(p.category), ''), '') AS category,
        p.holding_amount,
        COALESCE(NULLIF(TRIM(p.note), ''), '') AS note
    FROM fund_positions p
    JOIN app_users u ON u.id = p.user_id
    JOIN (
        SELECT
            user_id,
            COALESCE(NULLIF(TRIM(fund_code), ''), '') AS fund_code_key,
            COALESCE(NULLIF(TRIM(fund_name), ''), '') AS fund_name_key
        FROM fund_positions
        GROUP BY user_id, fund_code_key, fund_name_key
        HAVING COUNT(*) > 1
    ) dup
      ON dup.user_id = p.user_id
     AND dup.fund_code_key = COALESCE(NULLIF(TRIM(p.fund_code), ''), '')
     AND dup.fund_name_key = COALESCE(NULLIF(TRIM(p.fund_name), ''), '')
    ORDER BY u.user_id, fund_name, p.id;
    """
    with connection.cursor() as cursor:
        cursor.execute(query)
        return cursor.fetchall()


def backup_duplicate_rows(rows: list[tuple]) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"duplicate_positions_backup_{timestamp}.csv"
    with backup_path.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(
            [
                "id",
                "user_id",
                "owner",
                "fund_code",
                "fund_name",
                "category",
                "holding_amount",
                "note",
            ]
        )
        writer.writerows(rows)
    return backup_path


def delete_duplicate_rows(connection) -> int:
    cleanup_sql = """
    WITH ranked AS (
        SELECT
            id,
            ROW_NUMBER() OVER (
                PARTITION BY
                    user_id,
                    COALESCE(NULLIF(TRIM(fund_code), ''), ''),
                    COALESCE(NULLIF(TRIM(fund_name), ''), '')
                ORDER BY
                    CASE WHEN holding_amount IS NOT NULL THEN 0 ELSE 1 END,
                    id DESC
            ) AS rn
        FROM fund_positions
    )
    DELETE FROM fund_positions
    WHERE id IN (
        SELECT id
        FROM ranked
        WHERE rn > 1
    );
    """
    with connection.cursor() as cursor:
        cursor.execute(cleanup_sql)
        deleted_count = cursor.rowcount or 0
    connection.commit()
    return deleted_count


def main() -> None:
    database_url = load_database_url()
    with connect(database_url, connect_timeout=5) as connection:
        duplicate_rows = fetch_duplicate_rows(connection)
        if not duplicate_rows:
            print("NO_DUPLICATES")
            return

        backup_path = backup_duplicate_rows(duplicate_rows)
        deleted_count = delete_duplicate_rows(connection)
        print(f"BACKUP={backup_path}")
        print(f"DELETED_ROWS={deleted_count}")


if __name__ == "__main__":
    main()
