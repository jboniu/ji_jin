"""Service helpers for quote-related API endpoints."""

from __future__ import annotations

from fund_quote import get_fund_history, get_fund_quote
from fund_name_service import resolve_preferred_fund_code
from user_service import get_user_by_id, get_user_positions, repair_user_position_codes


def build_fallback_quote_payload(fund_code: str, fund_name: str, message: str) -> dict:
    """Return a readable fallback payload when quote lookup fails."""
    return {
        "fund_code": fund_code,
        "fund_name": fund_name,
        "display_nav": None,
        "display_nav_type": "unknown",
        "display_nav_label": "暂无行情",
        "primary_nav_label": "当前重点",
        "primary_nav_title": "最近净值",
        "primary_nav_value": None,
        "primary_nav_time_label": "净值日期",
        "primary_nav_time_text": "--",
        "official_nav": None,
        "official_nav_date": None,
        "estimated_nav": None,
        "estimated_nav_time": None,
        "last_available_nav": None,
        "last_available_nav_date": None,
        "daily_change_rate": None,
        "weekly_change_rate": None,
        "monthly_change_rate": None,
        "intraday_change_rate": None,
        "intraday_change_text": "--",
        "intraday_change_label": "当前涨幅",
        "today_change_rate": None,
        "today_change_text": "--",
        "today_change_label": "当前涨幅",
        "today_change_time_label": "更新时间",
        "today_change_time_text": "--",
        "market_status": "unknown",
        "market_hint": "",
        "is_estimated_used": False,
        "data_source": {},
        "updated_at": None,
        "status": "partial",
        "message": message,
    }


def get_quote_payload(fund_code: str, fund_name: str = "") -> dict:
    """Return a normalized single-fund quote payload."""
    preferred_code = resolve_preferred_fund_code(fund_name=fund_name, current_code=fund_code)
    if preferred_code or fund_code:
        result = get_fund_quote(fund_code=preferred_code or fund_code, fund_name=fund_name)
        if result.get("status") != "error":
            return result
        return build_fallback_quote_payload(
            fund_code=preferred_code or fund_code,
            fund_name=fund_name or result.get("fund_name", ""),
            message="该基金暂时无法拉取行情，当前仅展示本地持仓信息",
        )
    return build_fallback_quote_payload(
        fund_code="",
        fund_name=fund_name,
        message="暂未匹配到有效基金代码，当前仅展示本地持仓信息",
    )


def get_user_quotes_payload(user_id: str) -> dict | None:
    """Return normalized quote items for every position of one user."""
    repair_user_position_codes(user_id)
    user = get_user_by_id(user_id)
    if user is None:
        return None
    positions = get_user_positions(user_id)
    if positions is None:
        return None

    items: list[dict] = []
    for position in positions:
        fund_name = str(position.get("fund_name", "")).strip()
        raw_code = str(position.get("fund_code", "")).strip()
        preferred_code = resolve_preferred_fund_code(fund_name=fund_name, current_code=raw_code)
        quote = get_fund_quote(
            fund_code=preferred_code or raw_code,
            fund_name=fund_name,
        )
        quote["holding_amount"] = position.get("holding_amount")
        quote["category"] = position.get("category", "")
        quote["note"] = position.get("note", "")
        items.append(quote)

    return {
        "user_id": user_id,
        "owner": user.get("owner", ""),
        "items": items,
        "total": len(items),
    }


def get_user_quote_trends_payload(user_id: str, period: str = "week", count: int = 8) -> dict | None:
    """Return lightweight history previews for every valid fund code of one user."""
    repair_user_position_codes(user_id)
    user = get_user_by_id(user_id)
    if user is None:
        return None
    positions = get_user_positions(user_id)
    if positions is None:
        return None

    items: list[dict] = []
    for position in positions:
        fund_code = str(position.get("fund_code", "")).strip()
        if not fund_code.isdigit() or len(fund_code) != 6:
            continue
        history_items = get_fund_history(fund_code=fund_code, period=period, count=count)
        items.append(
            {
                "fund_code": fund_code,
                "items": history_items,
                "total": len(history_items),
            }
        )

    return {
        "user_id": user_id,
        "period": period,
        "count": count,
        "items": items,
        "total": len(items),
    }
