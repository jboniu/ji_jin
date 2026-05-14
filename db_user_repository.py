"""Database-backed user and position read helpers."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from database import get_database_url, is_database_configured


def _connect():
    from psycopg import connect

    return connect(get_database_url(), connect_timeout=3)


def is_db_user_repository_available() -> bool:
    """Return whether database-backed user reads can be attempted."""
    return is_database_configured()


def _build_user_map(rows: list[tuple]) -> dict[str, dict]:
    grouped: dict[str, dict] = {}
    for row in rows:
        (
            user_id,
            username,
            password_hash,
            owner,
            subscribe_email_reports,
            currency,
            email,
            fund_code,
            fund_name,
            category,
            holding_amount,
            note,
        ) = row

        if user_id not in grouped:
            grouped[user_id] = {
                "user_id": user_id,
                "username": username,
                "password": password_hash,
                "owner": owner,
                "subscribe_email_reports": bool(subscribe_email_reports),
                "currency": currency,
                "email_to": [],
                "positions": [],
            }

        user = grouped[user_id]
        if email and email not in user["email_to"]:
            user["email_to"].append(email)

        if fund_name:
            user["positions"].append(
                {
                    "fund_code": fund_code or "",
                    "fund_name": fund_name,
                    "category": category or "",
                    "holding_amount": float(holding_amount) if holding_amount is not None else None,
                    "note": note or "",
                }
            )
    return grouped


def load_all_users_from_db() -> list[dict]:
    """Load all users and positions from PostgreSQL."""
    query = """
        SELECT
            u.user_id,
            u.username,
            u.password_hash,
            u.owner,
            u.subscribe_email_reports,
            u.currency,
            e.email,
            p.fund_code,
            p.fund_name,
            p.category,
            p.holding_amount,
            p.note
        FROM app_users u
        LEFT JOIN user_emails e ON e.user_id = u.id
        LEFT JOIN fund_positions p ON p.user_id = u.id
        ORDER BY u.id, p.id
    """
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()
    return list(_build_user_map(rows).values())


def load_user_by_id_from_db(user_id: str) -> dict | None:
    """Load one user and positions from PostgreSQL."""
    query = """
        SELECT
            u.user_id,
            u.username,
            u.password_hash,
            u.owner,
            u.subscribe_email_reports,
            u.currency,
            e.email,
            p.fund_code,
            p.fund_name,
            p.category,
            p.holding_amount,
            p.note
        FROM app_users u
        LEFT JOIN user_emails e ON e.user_id = u.id
        LEFT JOIN fund_positions p ON p.user_id = u.id
        WHERE u.user_id = %s
        ORDER BY p.id
    """
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (user_id,))
            rows = cursor.fetchall()
    users = _build_user_map(rows)
    return users.get(user_id)


def load_user_by_username_from_db(username: str) -> dict | None:
    """Load one user and positions from PostgreSQL by username."""
    query = """
        SELECT
            u.user_id,
            u.username,
            u.password_hash,
            u.owner,
            u.subscribe_email_reports,
            u.currency,
            e.email,
            p.fund_code,
            p.fund_name,
            p.category,
            p.holding_amount,
            p.note
        FROM app_users u
        LEFT JOIN user_emails e ON e.user_id = u.id
        LEFT JOIN fund_positions p ON p.user_id = u.id
        WHERE u.username = %s
        ORDER BY p.id
    """
    with _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (username,))
            rows = cursor.fetchall()
    users = _build_user_map(rows)
    return next(iter(users.values()), None)


def _get_app_user_pk(cursor, user_id: str) -> int | None:
    cursor.execute("SELECT id FROM app_users WHERE user_id = %s", (user_id,))
    row = cursor.fetchone()
    return row[0] if row else None


def update_user_profile_in_db(
    user_id: str,
    owner: str,
    email_to: list[str],
    subscribe_email_reports: bool,
) -> dict | None:
    """Update one user profile in PostgreSQL."""
    with _connect() as connection:
        with connection.cursor() as cursor:
            app_user_id = _get_app_user_pk(cursor, user_id)
            if app_user_id is None:
                return None
            cursor.execute(
                """
                UPDATE app_users
                SET owner = %s, subscribe_email_reports = %s, updated_at = NOW()
                WHERE id = %s
                """,
                (owner.strip(), subscribe_email_reports, app_user_id),
            )
            cursor.execute("DELETE FROM user_emails WHERE user_id = %s", (app_user_id,))
            for email in email_to:
                cleaned = str(email).strip()
                if not cleaned:
                    continue
                cursor.execute(
                    "INSERT INTO user_emails (user_id, email) VALUES (%s, %s)",
                    (app_user_id, cleaned),
                )
        connection.commit()
    return load_user_by_id_from_db(user_id)


def replace_user_positions_in_db(user_id: str, positions: list[dict]) -> dict | None:
    """Replace one user's positions in PostgreSQL."""
    with _connect() as connection:
        with connection.cursor() as cursor:
            app_user_id = _get_app_user_pk(cursor, user_id)
            if app_user_id is None:
                return None
            cursor.execute("DELETE FROM fund_positions WHERE user_id = %s", (app_user_id,))
            for position in positions:
                fund_name = str(position.get("fund_name", "")).strip()
                if not fund_name:
                    continue
                cursor.execute(
                    """
                    INSERT INTO fund_positions (user_id, fund_code, fund_name, category, holding_amount, note)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        app_user_id,
                        str(position.get("fund_code", "")).strip(),
                        fund_name,
                        str(position.get("category", "")).strip(),
                        position.get("holding_amount"),
                        str(position.get("note", "")).strip(),
                    ),
                )
        connection.commit()
    return load_user_by_id_from_db(user_id)


def update_user_password_in_db(user_id: str, new_password: str) -> dict | None:
    """Update one user's password in PostgreSQL."""
    with _connect() as connection:
        with connection.cursor() as cursor:
            app_user_id = _get_app_user_pk(cursor, user_id)
            if app_user_id is None:
                return None
            cursor.execute(
                """
                UPDATE app_users
                SET password_hash = %s, updated_at = NOW()
                WHERE id = %s
                """,
                (str(new_password), app_user_id),
            )
        connection.commit()
    return load_user_by_id_from_db(user_id)
