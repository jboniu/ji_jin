"""Import local users.json data into PostgreSQL."""

from __future__ import annotations

from database import get_database_url
from portfolio import load_portfolio, load_users, normalize_single_user_portfolio


DEFAULT_PASSWORD = "123456"


def _load_source_users() -> list[dict]:
    users = load_users()
    if users:
        return users
    return [normalize_single_user_portfolio(load_portfolio())]


def seed_users() -> dict:
    """Insert users, emails, and positions into PostgreSQL."""
    database_url = get_database_url()
    if not database_url:
        raise RuntimeError("DATABASE_URL 未配置，无法导入用户数据")

    from psycopg import connect

    users = _load_source_users()
    created_users = 0
    created_positions = 0

    with connect(database_url, connect_timeout=5) as connection:
        with connection.cursor() as cursor:
            for user in users:
                user_id = str(user.get("user_id", "")).strip()
                username = str(user.get("username") or user_id).strip()
                owner = str(user.get("owner", "")).strip() or user_id
                currency = str(user.get("currency", "CNY")).strip() or "CNY"
                password_hash = str(user.get("password") or DEFAULT_PASSWORD)

                cursor.execute(
                    """
                    INSERT INTO app_users (user_id, username, password_hash, owner, currency)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        username = EXCLUDED.username,
                        password_hash = EXCLUDED.password_hash,
                        owner = EXCLUDED.owner,
                        currency = EXCLUDED.currency,
                        updated_at = NOW()
                    RETURNING id
                    """,
                    (user_id, username, password_hash, owner, currency),
                )
                app_user_id = cursor.fetchone()[0]
                created_users += 1

                cursor.execute("DELETE FROM user_emails WHERE user_id = %s", (app_user_id,))
                cursor.execute("DELETE FROM fund_positions WHERE user_id = %s", (app_user_id,))

                for email in user.get("email_to", []):
                    cleaned = str(email).strip()
                    if not cleaned:
                        continue
                    cursor.execute(
                        "INSERT INTO user_emails (user_id, email) VALUES (%s, %s)",
                        (app_user_id, cleaned),
                    )

                for position in user.get("positions", []):
                    fund_code = str(position.get("fund_code", "")).strip()
                    fund_name = str(position.get("fund_name", "")).strip()
                    if not fund_name:
                        continue
                    category = str(position.get("category", "")).strip()
                    note = str(position.get("note", "")).strip()
                    holding_amount = position.get("holding_amount")
                    cursor.execute(
                        """
                        INSERT INTO fund_positions (user_id, fund_code, fund_name, category, holding_amount, note)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (app_user_id, fund_code, fund_name, category, holding_amount, note),
                    )
                    created_positions += 1
        connection.commit()

    return {
        "users": created_users,
        "positions": created_positions,
    }


if __name__ == "__main__":
    result = seed_users()
    print(f"seeded_users={result['users']}")
    print(f"seeded_positions={result['positions']}")
