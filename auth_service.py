"""Simple local authentication helpers for the mini-program."""

from __future__ import annotations

import json
import secrets
from datetime import datetime

from database import is_data_backend_strict
from db_user_repository import (
    is_db_user_repository_available,
    load_user_by_id_from_db,
    load_user_by_username_from_db,
    update_user_password_in_db,
)
from portfolio import USERS_PATH, load_portfolio, load_users, normalize_single_user_portfolio


SESSIONS: dict[str, dict] = {}
DEFAULT_PASSWORD = "123456"


def _load_auth_users() -> list[dict]:
    """Load users from users.json, with legacy single-user fallback."""
    if is_db_user_repository_available():
        try:
            db_user = load_user_by_username_from_db("__probe__")
            _ = db_user  # quiet lint-style warnings in simple script environment
        except Exception:
            pass
    users = load_users()
    if users:
        return users
    return [normalize_single_user_portfolio(load_portfolio())]


def _resolve_username(user: dict) -> str:
    """Return the configured login name, defaulting to user_id."""
    return str(user.get("username") or user.get("user_id") or "").strip()


def _resolve_password(user: dict) -> str:
    """Return the configured password, defaulting to a simple local password."""
    return str(user.get("password") or DEFAULT_PASSWORD)


def authenticate_user(username: str, password: str) -> dict | None:
    """Validate one username/password pair and return a lightweight session."""
    normalized_username = username.strip()
    if not normalized_username or not password:
        return None

    if is_db_user_repository_available():
        try:
            db_user = load_user_by_username_from_db(normalized_username)
            if db_user is not None:
                if _resolve_password(db_user) != password:
                    return None
                token = secrets.token_urlsafe(24)
                session = {
                    "token": token,
                    "user_id": str(db_user.get("user_id", "")).strip(),
                    "username": _resolve_username(db_user),
                    "owner": str(db_user.get("owner", "")).strip(),
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "auth_backend": "postgres",
                }
                SESSIONS[token] = session
                return session
        except Exception:
            if is_data_backend_strict():
                raise

    for user in _load_auth_users():
        if _resolve_username(user) != normalized_username:
            continue
        if _resolve_password(user) != password:
            return None

        token = secrets.token_urlsafe(24)
        session = {
            "token": token,
            "user_id": str(user.get("user_id", "")).strip(),
            "username": _resolve_username(user),
            "owner": str(user.get("owner", "")).strip(),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "auth_backend": "json",
        }
        SESSIONS[token] = session
        return session

    return None


def change_user_password(user_id: str, old_password: str, new_password: str) -> dict | None:
    """Change one user's password with old-password verification."""
    current_password = str(old_password)
    next_password = str(new_password)
    if not current_password or not next_password:
        raise ValueError("old_password and new_password are required")
    if current_password == next_password:
        raise ValueError("new password must be different from old password")

    if is_db_user_repository_available():
        try:
            db_user = load_user_by_id_from_db(user_id)
            if db_user is not None:
                if _resolve_password(db_user) != current_password:
                    raise ValueError("old password is incorrect")
                updated_user = update_user_password_in_db(user_id, next_password)
                if updated_user is None:
                    return None
                return {
                    "status": "ok",
                    "user_id": user_id,
                    "message": "密码修改成功",
                    "auth_backend": "postgres",
                }
        except ValueError:
            raise
        except Exception:
            if is_data_backend_strict():
                raise

    users = load_users()
    if not users:
        return None

    updated = False
    for user in users:
        if str(user.get("user_id", "")).strip() != user_id:
            continue
        if _resolve_password(user) != current_password:
            raise ValueError("old password is incorrect")
        user["password"] = next_password
        updated = True
        break

    if not updated:
        return None

    USERS_PATH.write_text(
        json.dumps({"users": users}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "status": "ok",
        "user_id": user_id,
        "message": "密码修改成功",
        "auth_backend": "json",
    }
