"""Helpers for loading user and position data for the API layer."""

from __future__ import annotations

import json
from pathlib import Path

from database import is_data_backend_strict
from db_user_repository import (
    is_db_user_repository_available,
    load_all_users_from_db,
    load_user_by_id_from_db,
    replace_user_positions_in_db,
    update_user_profile_in_db,
)
from fund_name_service import resolve_preferred_fund_code
from portfolio import USERS_PATH, load_portfolio, load_users, normalize_single_user_portfolio


REPORTS_DIR = Path("reports")


def _raise_if_data_backend_strict() -> None:
    if is_data_backend_strict():
        raise


def get_all_users() -> list[dict]:
    """Return configured users, falling back to the legacy single-user file."""
    if is_db_user_repository_available():
        try:
            db_users = load_all_users_from_db()
            if db_users:
                return db_users
        except Exception:
            _raise_if_data_backend_strict()
    users = load_users()
    if users:
        return users
    return [normalize_single_user_portfolio(load_portfolio())]


def get_user_by_id(user_id: str) -> dict | None:
    """Find one user by user_id."""
    if is_db_user_repository_available():
        try:
            db_user = load_user_by_id_from_db(user_id)
            if db_user is not None:
                return db_user
        except Exception:
            _raise_if_data_backend_strict()
    for user in get_all_users():
        if str(user.get("user_id", "")).strip() == user_id:
            return user
    return None


def _is_valid_fund_code(value: str) -> bool:
    return value.isdigit() and len(value) == 6


def _safe_float(value: object) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_position_shape(position: dict) -> dict:
    """Normalize one position row for the amount-only data model."""
    normalized = dict(position)
    amount = _safe_float(normalized.get("holding_amount"))
    normalized["holding_amount"] = round(amount, 2) if amount is not None else None
    normalized.pop("allocation_percent", None)
    return normalized


def _merge_position_items(existing: dict, incoming: dict) -> dict:
    """Merge two duplicate position rows into one normalized row."""
    existing_code = str(existing.get("fund_code", "")).strip()
    incoming_code = str(incoming.get("fund_code", "")).strip()
    existing_name = str(existing.get("fund_name", "")).strip()
    incoming_name = str(incoming.get("fund_name", "")).strip()

    merged = dict(existing)
    if _is_valid_fund_code(incoming_code):
        merged["fund_code"] = incoming_code
    elif not _is_valid_fund_code(existing_code):
        merged["fund_code"] = incoming_code or existing_code

    merged["fund_name"] = incoming_name if len(incoming_name) > len(existing_name) else existing_name

    existing_amount = _safe_float(existing.get("holding_amount"))
    incoming_amount = _safe_float(incoming.get("holding_amount"))
    preferred_amount = incoming_amount if incoming_amount is not None else existing_amount
    merged["holding_amount"] = round(preferred_amount, 2) if preferred_amount is not None else None

    existing_category = str(existing.get("category", "")).strip()
    incoming_category = str(incoming.get("category", "")).strip()
    merged["category"] = incoming_category or existing_category

    notes: list[str] = []
    for note in [existing.get("note", ""), incoming.get("note", "")]:
        cleaned = str(note).strip()
        if cleaned and cleaned not in notes:
            notes.append(cleaned)
    merged["note"] = "；".join(notes)
    merged.pop("allocation_percent", None)
    return merged


def _deduplicate_positions(positions: list[dict]) -> tuple[list[dict], bool]:
    """Deduplicate positions by fund code first, then fund name."""
    merged_map: dict[str, dict] = {}
    order: list[str] = []
    changed = False
    original_snapshot = [dict(item) for item in positions]

    for raw_position in positions:
        position = _normalize_position_shape(raw_position)
        fund_code = str(position.get("fund_code", "")).strip()
        fund_name = str(position.get("fund_name", "")).strip()
        key = f"code:{fund_code}" if _is_valid_fund_code(fund_code) else f"name:{fund_name}"
        if key in merged_map:
            merged_map[key] = _merge_position_items(merged_map[key], position)
            changed = True
            continue
        merged_map[key] = dict(position)
        order.append(key)

    result = [merged_map[key] for key in order]
    if len(result) != len(positions) or result != original_snapshot:
        changed = True
    return result, changed


def build_user_summary(user: dict) -> dict:
    """Return a lightweight user payload for API responses."""
    return {
        "user_id": user.get("user_id", ""),
        "owner": user.get("owner", ""),
        "email_to": user.get("email_to", []),
        "subscribe_email_reports": bool(user.get("subscribe_email_reports", False)),
        "currency": user.get("currency", "CNY"),
        "position_count": len(user.get("positions", [])),
    }


def get_user_positions(user_id: str) -> list[dict] | None:
    """Return the positions list for one user."""
    if is_db_user_repository_available():
        try:
            user = get_user_by_id(user_id)
            if user is None:
                return None
            positions, _ = _deduplicate_positions(user.get("positions", []))
            return [_normalize_position_shape(item) for item in positions]
        except Exception:
            _raise_if_data_backend_strict()
    repair_user_position_codes(user_id)
    deduplicate_user_positions(user_id)
    user = get_user_by_id(user_id)
    if user is None:
        return None
    return [_normalize_position_shape(item) for item in user.get("positions", [])]


def deduplicate_user_positions(user_id: str) -> dict | None:
    """Deduplicate one user's positions and persist the merged result."""
    if is_db_user_repository_available():
        try:
            user = get_user_by_id(user_id)
            if user is None:
                return None
            deduplicated_positions, _ = _deduplicate_positions(user.get("positions", []))
            return replace_user_positions_in_db(user_id, deduplicated_positions)
        except Exception:
            _raise_if_data_backend_strict()

    users = load_users()
    if not users:
        return None

    updated_user = None
    changed = False
    for user in users:
        if str(user.get("user_id", "")).strip() != user_id:
            continue
        deduplicated_positions, positions_changed = _deduplicate_positions(user.get("positions", []))
        user["positions"] = deduplicated_positions
        updated_user = user
        changed = positions_changed
        break

    if updated_user is None:
        return None

    if changed:
        USERS_PATH.write_text(
            json.dumps({"users": users}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return updated_user


def repair_user_position_codes(user_id: str) -> dict | None:
    """Repair missing or invalid fund codes for one user's positions."""
    if is_db_user_repository_available():
        try:
            user = get_user_by_id(user_id)
            if user is None:
                return None
            changed = False
            positions = []
            for position in user.get("positions", []):
                next_position = dict(position)
                current_code = str(next_position.get("fund_code", "")).strip()
                resolved_code = resolve_preferred_fund_code(
                    fund_name=next_position.get("fund_name", ""),
                    current_code=current_code,
                )
                if resolved_code and resolved_code != current_code:
                    next_position["fund_code"] = resolved_code
                    changed = True
                positions.append(next_position)
            if changed:
                return replace_user_positions_in_db(user_id, positions)
            return user
        except Exception:
            _raise_if_data_backend_strict()

    users = load_users()
    if not users:
        return None

    updated_user = None
    changed = False
    for user in users:
        if str(user.get("user_id", "")).strip() != user_id:
            continue

        for position in user.get("positions", []):
            current_code = str(position.get("fund_code", "")).strip()
            resolved_code = resolve_preferred_fund_code(
                fund_name=position.get("fund_name", ""),
                current_code=current_code,
            )
            if resolved_code and resolved_code != current_code:
                position["fund_code"] = resolved_code
                changed = True

        updated_user = user
        break

    if updated_user is None:
        return None

    if changed:
        USERS_PATH.write_text(
            json.dumps({"users": users}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return updated_user


def update_user_profile(
    user_id: str,
    owner: str,
    email_to: list[str],
    subscribe_email_reports: bool,
) -> dict | None:
    """Update one user's basic profile fields and persist them to users.json."""
    if is_db_user_repository_available():
        try:
            existing_user = get_user_by_id(user_id)
            if existing_user is None:
                return None
            old_owner = str(existing_user.get("owner", "")).strip()
            updated_user = update_user_profile_in_db(
                user_id=user_id,
                owner=owner,
                email_to=email_to,
                subscribe_email_reports=subscribe_email_reports,
            )
            if updated_user is None:
                return None
            _rename_user_reports(old_owner=old_owner, new_owner=str(updated_user.get("owner", "")).strip())
            return updated_user
        except Exception:
            _raise_if_data_backend_strict()

    users = load_users()
    if not users:
        return None

    updated_user = None
    for user in users:
        if str(user.get("user_id", "")).strip() != user_id:
            continue
        old_owner = str(user.get("owner", "")).strip()
        user["owner"] = owner.strip()
        user["email_to"] = [item.strip() for item in email_to if item.strip()]
        user["subscribe_email_reports"] = bool(subscribe_email_reports)
        updated_user = user
        _rename_user_reports(old_owner=old_owner, new_owner=user["owner"])
        break

    if updated_user is None:
        return None

    USERS_PATH.write_text(
        json.dumps({"users": users}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return updated_user


def _rename_user_reports(old_owner: str, new_owner: str) -> None:
    """Keep historical reports reachable after a user renames themselves."""
    old_owner = old_owner.strip()
    new_owner = new_owner.strip()
    if not old_owner or not new_owner or old_owner == new_owner:
        return

    REPORTS_DIR.mkdir(exist_ok=True)
    for path in REPORTS_DIR.iterdir():
        if not path.is_file():
            continue
        if old_owner not in path.name:
            continue
        new_name = path.name.replace(old_owner, new_owner)
        target = path.with_name(new_name)
        if target.exists():
            continue
        try:
            path.rename(target)
        except OSError:
            continue


def add_user_position(user_id: str, position: dict) -> dict | None:
    """Add one position for a user and persist it."""
    if is_db_user_repository_available():
        try:
            user = get_user_by_id(user_id)
            if user is None:
                return None
            positions = user.get("positions", []) + [_normalize_position_shape(position)]
            deduplicated_positions, _ = _deduplicate_positions(positions)
            return replace_user_positions_in_db(user_id, deduplicated_positions)
        except Exception:
            _raise_if_data_backend_strict()

    users = load_users()
    if not users:
        return None

    updated_user = None
    for user in users:
        if str(user.get("user_id", "")).strip() != user_id:
            continue
        positions = user.setdefault("positions", [])
        positions.append(_normalize_position_shape(position))
        updated_user = user
        break

    if updated_user is None:
        return None

    deduplicated_positions, _ = _deduplicate_positions(updated_user.get("positions", []))
    updated_user["positions"] = deduplicated_positions
    USERS_PATH.write_text(
        json.dumps({"users": users}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return updated_user


def update_user_position(user_id: str, fund_code: str, payload: dict) -> dict | None:
    """Update one existing position by fund code."""
    if is_db_user_repository_available():
        try:
            user = get_user_by_id(user_id)
            if user is None:
                return None
            updated_positions = []
            found = False
            normalized_payload = _normalize_position_shape(payload)
            for position in user.get("positions", []):
                if str(position.get("fund_code", "")).strip() == fund_code:
                    next_position = dict(position)
                    next_position.update(normalized_payload)
                    updated_positions.append(next_position)
                    found = True
                else:
                    updated_positions.append(dict(position))
            if not found:
                return None
            deduplicated_positions, _ = _deduplicate_positions(updated_positions)
            return replace_user_positions_in_db(user_id, deduplicated_positions)
        except Exception:
            _raise_if_data_backend_strict()

    users = load_users()
    if not users:
        return None

    updated_user = None
    for user in users:
        if str(user.get("user_id", "")).strip() != user_id:
            continue
        for position in user.get("positions", []):
            if str(position.get("fund_code", "")).strip() != fund_code:
                continue
            position.update(_normalize_position_shape(payload))
            updated_user = user
            break
        if updated_user is not None:
            break

    if updated_user is None:
        return None

    deduplicated_positions, _ = _deduplicate_positions(updated_user.get("positions", []))
    updated_user["positions"] = deduplicated_positions
    USERS_PATH.write_text(
        json.dumps({"users": users}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return updated_user


def delete_user_position(user_id: str, fund_code: str) -> dict | None:
    """Delete one existing position by fund code."""
    if is_db_user_repository_available():
        try:
            user = get_user_by_id(user_id)
            if user is None:
                return None
            positions = user.get("positions", [])
            remaining = [dict(item) for item in positions if str(item.get("fund_code", "")).strip() != fund_code]
            if len(remaining) == len(positions):
                return None
            deduplicated_positions, _ = _deduplicate_positions(remaining)
            return replace_user_positions_in_db(user_id, deduplicated_positions)
        except Exception:
            _raise_if_data_backend_strict()

    users = load_users()
    if not users:
        return None

    updated_user = None
    for user in users:
        if str(user.get("user_id", "")).strip() != user_id:
            continue
        positions = user.get("positions", [])
        remaining = [item for item in positions if str(item.get("fund_code", "")).strip() != fund_code]
        if len(remaining) == len(positions):
            return None
        user["positions"] = remaining
        updated_user = user
        break

    if updated_user is None:
        return None

    deduplicated_positions, _ = _deduplicate_positions(updated_user.get("positions", []))
    updated_user["positions"] = deduplicated_positions
    USERS_PATH.write_text(
        json.dumps({"users": users}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return updated_user


def upsert_user_positions(user_id: str, positions: list[dict]) -> dict | None:
    """Merge imported positions into one user's existing holdings."""
    result = merge_imported_positions(user_id=user_id, positions=positions)
    if result is None:
        return None
    return result["user"]


def merge_imported_positions(user_id: str, positions: list[dict]) -> dict | None:
    """Merge imported positions into one user's existing holdings and report changes."""
    if is_db_user_repository_available():
        try:
            user = get_user_by_id(user_id)
            if user is None:
                return None

            current_positions = [dict(item) for item in user.get("positions", [])]
            created_count = 0
            updated_count = 0
            for raw_incoming in positions:
                incoming = _normalize_position_shape(raw_incoming)
                incoming_code = str(incoming.get("fund_code", "")).strip()
                incoming_name = str(incoming.get("fund_name", "")).strip()
                resolved_code = resolve_preferred_fund_code(
                    fund_name=incoming_name,
                    current_code=incoming_code,
                )
                if resolved_code and resolved_code != incoming_code:
                    incoming["fund_code"] = resolved_code
                    incoming_code = resolved_code

                matched = None
                for existing in current_positions:
                    existing_code = str(existing.get("fund_code", "")).strip()
                    existing_name = str(existing.get("fund_name", "")).strip()
                    if incoming_code and existing_code == incoming_code:
                        matched = existing
                        break
                    if incoming_name and existing_name == incoming_name:
                        matched = existing
                        break

                if matched is not None:
                    for key, value in incoming.items():
                        if key == "fund_code" and not str(value or "").strip():
                            continue
                        if key == "category" and not str(value or "").strip():
                            continue
                        matched[key] = value
                    updated_count += 1
                else:
                    current_positions.append(incoming)
                    created_count += 1

            deduplicated_positions, _ = _deduplicate_positions(current_positions)
            updated_user = replace_user_positions_in_db(user_id, deduplicated_positions)
            if updated_user is None:
                return None
            return {
                "user": updated_user,
                "created_count": created_count,
                "updated_count": updated_count,
            }
        except Exception:
            _raise_if_data_backend_strict()

    users = load_users()
    if not users:
        return None

    updated_user = None
    created_count = 0
    updated_count = 0
    for user in users:
        if str(user.get("user_id", "")).strip() != user_id:
            continue

        current_positions = user.setdefault("positions", [])
        for raw_incoming in positions:
            incoming = _normalize_position_shape(raw_incoming)
            incoming_code = str(incoming.get("fund_code", "")).strip()
            incoming_name = str(incoming.get("fund_name", "")).strip()
            resolved_code = resolve_preferred_fund_code(
                fund_name=incoming_name,
                current_code=incoming_code,
            )
            if resolved_code and resolved_code != incoming_code:
                incoming["fund_code"] = resolved_code
                incoming_code = resolved_code

            matched = None
            for existing in current_positions:
                existing_code = str(existing.get("fund_code", "")).strip()
                existing_name = str(existing.get("fund_name", "")).strip()
                if incoming_code and existing_code == incoming_code:
                    matched = existing
                    break
                if incoming_name and existing_name == incoming_name:
                    matched = existing
                    break

            if matched is not None:
                incoming_code = str(incoming.get("fund_code", "")).strip()
                for key, value in incoming.items():
                    if key == "fund_code" and not incoming_code:
                        continue
                    if key == "category" and not str(value or "").strip():
                        continue
                    matched[key] = value
                matched.pop("allocation_percent", None)
                updated_count += 1
            else:
                current_positions.append(incoming)
                created_count += 1

        updated_user = user
        break

    if updated_user is None:
        return None

    deduplicated_positions, _ = _deduplicate_positions(updated_user.get("positions", []))
    updated_user["positions"] = deduplicated_positions
    USERS_PATH.write_text(
        json.dumps({"users": users}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "user": updated_user,
        "created_count": created_count,
        "updated_count": updated_count,
    }
