"""Fetch free fund NAV and estimate data for a single fund."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta, timezone
import json
from pathlib import Path
import re
from typing import Any

import requests

from app_logging import get_logger


try:
    import akshare as ak
except ImportError:  # pragma: no cover - handled at runtime for missing optional dependency
    ak = None


DEFAULT_TIMEOUT = 10
ESTIMATE_URL_TEMPLATE = "http://fundgz.1234567.com.cn/js/{fund_code}.js"
PINGZHONGDATA_URL_TEMPLATE = "http://fund.eastmoney.com/pingzhongdata/{fund_code}.js"
QUOTE_CACHE_PATH = Path("quote_cache.json")
QUOTE_CACHE_TTL_SECONDS = 300
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/135.0.0.0 Safari/537.36"
)

logger = get_logger("fund_quote")
HTTP_SESSION = requests.Session()
HTTP_SESSION.trust_env = False
SHANGHAI_TZ = timezone(timedelta(hours=8))

MARKET_HOLIDAYS_2026 = {
    date(2026, 1, 1),
    date(2026, 1, 2),
    date(2026, 1, 3),
    date(2026, 2, 15),
    date(2026, 2, 16),
    date(2026, 2, 17),
    date(2026, 2, 18),
    date(2026, 2, 19),
    date(2026, 2, 20),
    date(2026, 2, 21),
    date(2026, 2, 22),
    date(2026, 2, 23),
    date(2026, 4, 4),
    date(2026, 4, 5),
    date(2026, 4, 6),
    date(2026, 5, 1),
    date(2026, 5, 2),
    date(2026, 5, 3),
    date(2026, 5, 4),
    date(2026, 5, 5),
    date(2026, 6, 19),
    date(2026, 6, 20),
    date(2026, 6, 21),
    date(2026, 9, 25),
    date(2026, 9, 26),
    date(2026, 9, 27),
    date(2026, 10, 1),
    date(2026, 10, 2),
    date(2026, 10, 3),
    date(2026, 10, 4),
    date(2026, 10, 5),
    date(2026, 10, 6),
    date(2026, 10, 7),
}


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_str(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _parse_date(value: Any) -> date | None:
    text = _safe_str(value)
    if not text:
        return None

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _parse_datetime(value: Any) -> datetime | None:
    text = _safe_str(value)
    if not text:
        return None

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue

    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            parsed_time = datetime.strptime(text, fmt).time()
            return datetime.combine(_today(), parsed_time)
        except ValueError:
            continue

    parsed_date = _parse_date(text)
    if parsed_date is not None:
        return datetime.combine(parsed_date, datetime.min.time())
    return None


def _now_shanghai() -> datetime:
    return datetime.now(SHANGHAI_TZ)


def _today(now: datetime | None = None) -> date:
    current = now or _now_shanghai()
    if current.tzinfo is None:
        return current.date()
    return current.astimezone(SHANGHAI_TZ).date()


def _is_market_holiday(current_date: date) -> bool:
    if current_date.year == 2026:
        return current_date in MARKET_HOLIDAYS_2026
    return False


def _is_non_trading_calendar_day(current_date: date) -> bool:
    return current_date.weekday() >= 5 or _is_market_holiday(current_date)


def _has_same_day_official_update(
    official: dict[str, Any] | None,
    estimated: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> bool:
    current_date = _today(now)
    official_date = _parse_date((official or {}).get("nav_date"))
    if official_date == current_date and _safe_float((official or {}).get("nav")) is not None:
        return True

    estimated_official_date = _parse_date((estimated or {}).get("official_nav_date"))
    estimated_official_nav = _safe_float((estimated or {}).get("official_nav"))
    if estimated_official_date == current_date and estimated_official_nav is not None:
        return True

    return False


def _format_date(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _format_datetime(value: datetime | None) -> str | None:
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else None


def _format_signed_rate(value: float | None) -> str:
    if value is None:
        return "--"
    return f"{value:+.2f}%"


def _calc_change_rate(current_value: float | None, base_value: float | None) -> float | None:
    if current_value is None or base_value in (None, 0):
        return None
    return round((current_value - base_value) / base_value * 100, 2)


def _http_get(url: str, **kwargs):
    """Send one request without inheriting invalid proxy settings from the host."""
    return HTTP_SESSION.get(url, **kwargs)


def _get_market_status(now: datetime | None = None) -> str:
    current = now or _now_shanghai()
    current_date = _today(current)
    if _is_non_trading_calendar_day(current_date):
        return "non_trading_day"

    current_time = current.astimezone(SHANGHAI_TZ).time() if current.tzinfo else current.time()
    if current_time < time(9, 30):
        return "pre_open"
    if current_time < time(11, 30):
        return "trading"
    if current_time < time(13, 0):
        return "midday_break"
    if current_time < time(15, 0):
        return "trading"
    return "closed"


def _get_today_change_phase(now: datetime | None = None) -> str:
    current = now or _now_shanghai()
    current_date = _today(current)
    if _is_non_trading_calendar_day(current_date):
        return "non_trading_real"

    current_time = current.astimezone(SHANGHAI_TZ).time() if current.tzinfo else current.time()
    if current_time < time(9, 30):
        return "night_real"
    if current_time < time(15, 0):
        return "estimate_live"
    return "estimate_after_close"


def _build_intraday_change_payload(
    estimated: dict[str, Any] | None,
    trend: dict[str, Any] | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    trend = trend or {}
    market_status = _get_market_status(now)
    estimated_rate = _safe_float((estimated or {}).get("change_rate"))
    official_rate = _safe_float(trend.get("daily_change_rate"))

    if market_status == "trading" and estimated_rate is not None:
        intraday_rate = round(estimated_rate, 2)
        return {
            "intraday_change_rate": intraday_rate,
            "intraday_change_text": _format_signed_rate(intraday_rate),
            "intraday_change_label": "实时估涨",
            "market_status": market_status,
        }

    if market_status == "pre_open":
        return {
            "intraday_change_rate": None,
            "intraday_change_text": "暂未开盘",
            "intraday_change_label": "当前状态",
            "market_status": market_status,
        }

    closing_rate = official_rate if official_rate is not None else estimated_rate
    intraday_rate = round(closing_rate, 2) if closing_rate is not None else None
    return {
        "intraday_change_rate": intraday_rate,
        "intraday_change_text": _format_signed_rate(intraday_rate) if intraday_rate is not None else "--",
        "intraday_change_label": "当前涨幅",
        "market_status": market_status,
    }

def _build_today_change_payload(
    intraday_change: dict[str, Any] | None,
    estimated: dict[str, Any] | None = None,
    official: dict[str, Any] | None = None,
    trend: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    intraday_change = intraday_change or {}
    trend = trend or {}
    current = now or _now_shanghai()
    phase = _get_today_change_phase(current)
    has_today_official = _has_same_day_official_update(official, estimated=estimated, now=current)
    estimated_rate = _safe_float((estimated or {}).get("change_rate"))
    official_rate = _safe_float(trend.get("daily_change_rate"))
    latest_real_rate = round(official_rate, 2) if official_rate is not None else None
    latest_estimated_rate = round(estimated_rate, 2) if estimated_rate is not None else None

    def build_payload(rate: float | None, label: str) -> dict[str, Any]:
        return {
            "today_change_rate": rate,
            "today_change_text": _format_signed_rate(rate),
            "today_change_label": label,
        }

    if phase == "non_trading_real" and latest_real_rate is not None:
        return build_payload(latest_real_rate, "最后交易日真实涨幅")

    if phase == "night_real" and latest_real_rate is not None:
        return build_payload(latest_real_rate, "昨日真实涨幅")

    if phase == "estimate_live" and latest_estimated_rate is not None:
        return build_payload(latest_estimated_rate, "实时估涨")

    if phase == "estimate_after_close" and has_today_official and latest_real_rate is not None:
        return build_payload(latest_real_rate, "真实涨幅")

    if phase == "estimate_after_close" and latest_estimated_rate is not None:
        return build_payload(latest_estimated_rate, "今日估涨")

    if latest_estimated_rate is not None:
        return build_payload(latest_estimated_rate, "今日估涨")

    if latest_real_rate is not None:
        return build_payload(latest_real_rate, "真实涨幅")

    return {
        "today_change_rate": intraday_change.get("intraday_change_rate"),
        "today_change_text": intraday_change.get("intraday_change_text", "--"),
        "today_change_label": intraday_change.get("intraday_change_label", "当前涨幅"),
    }

def _build_today_change_time_payload(
    today_change: dict[str, Any] | None,
    estimated: dict[str, Any] | None = None,
    official: dict[str, Any] | None = None,
    last_available: dict[str, Any] | None = None,
    updated_at: str | None = None,
) -> dict[str, Any]:
    today_change = today_change or {}
    label = _safe_str(today_change.get("today_change_label"))

    if "估" in label:
        return {
            "today_change_time_label": "估值时间",
            "today_change_time_text": _safe_str((estimated or {}).get("nav_time")) or _safe_str(updated_at) or "暂无时间",
        }

    if "真实" in label:
        return {
            "today_change_time_label": "净值日期",
            "today_change_time_text": _safe_str((official or {}).get("nav_date"))
            or _safe_str((last_available or {}).get("nav_date"))
            or _safe_str(updated_at)
            or "暂无时间",
        }

    return {
        "today_change_time_label": "更新时间",
        "today_change_time_text": _safe_str(updated_at) or "暂无时间",
    }

def _build_market_hint_payload(market_status: str | None) -> dict[str, str]:
    status = _safe_str(market_status)
    if status == "non_trading_day":
        return {
            "market_hint": "非交易日，展示最后交易日真实涨幅",
        }
    if status == "pre_open":
        return {
            "market_hint": "开盘前，展示上一交易日真实涨幅",
        }
    if status == "closed":
        return {
            "market_hint": "收盘后，优先展示当日最新可用数据",
        }
    return {
        "market_hint": "",
    }

def _build_primary_nav_payload(
    market_status: str | None,
    official: dict[str, Any] | None,
    estimated: dict[str, Any] | None,
    last_available: dict[str, Any] | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    status = _safe_str(market_status)
    today_text = _format_date(_today(now))
    has_today_official = _has_same_day_official_update(official, estimated=estimated, now=now)

    if status == "trading":
        return {
            "primary_nav_label": "当前重点",
            "primary_nav_title": "盘中估值",
            "primary_nav_value": (estimated or {}).get("nav"),
            "primary_nav_time_label": "估值时间",
            "primary_nav_time_text": (estimated or {}).get("nav_time") or "暂无",
        }

    if status == "closed" and not has_today_official:
        return {
            "primary_nav_label": "当前重点",
            "primary_nav_title": "今日估值",
            "primary_nav_value": (estimated or {}).get("nav"),
            "primary_nav_time_label": "估值时间",
            "primary_nav_time_text": (estimated or {}).get("nav_time") or "暂无",
        }

    latest_nav = (last_available or {}).get("nav")
    latest_nav_date = (last_available or {}).get("nav_date")
    if latest_nav is None and official:
        latest_nav = official.get("nav")
        latest_nav_date = official.get("nav_date") or today_text

    return {
        "primary_nav_label": "当前重点",
        "primary_nav_title": "最近净值",
        "primary_nav_value": latest_nav,
        "primary_nav_time_label": "净值日期",
        "primary_nav_time_text": latest_nav_date or "暂无",
    }

def _hydrate_today_change_fields(result: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(result or {})
    intraday_change = {
        "intraday_change_rate": payload.get("intraday_change_rate"),
        "intraday_change_text": payload.get("intraday_change_text"),
        "intraday_change_label": payload.get("intraday_change_label"),
    }
    estimated_change_rate = _calc_change_rate(
        _safe_float(payload.get("estimated_nav")),
        _safe_float(payload.get("official_nav")),
    )
    estimated = {
        "change_rate": estimated_change_rate if estimated_change_rate is not None else payload.get("intraday_change_rate"),
    }
    official = {
        "nav_date": payload.get("official_nav_date"),
    }
    trend = {
        "daily_change_rate": payload.get("daily_change_rate"),
    }
    today_change = _build_today_change_payload(
        intraday_change,
        estimated=estimated,
        official=official,
        trend=trend,
    )
    payload.update(today_change)
    payload.update(
        _build_today_change_time_payload(
            today_change,
            estimated={"nav_time": payload.get("estimated_nav_time")},
            official=official,
            last_available={"nav_date": payload.get("last_available_nav_date")},
            updated_at=payload.get("updated_at"),
        )
    )
    payload.update(_build_market_hint_payload(payload.get("market_status")))
    return payload


def _parse_timestamp_ms(value: Any) -> date | None:
    try:
        timestamp = float(value) / 1000
    except (TypeError, ValueError):
        return None
    try:
        return datetime.fromtimestamp(timestamp).date()
    except (OverflowError, OSError, ValueError):
        return None


def _load_quote_cache() -> dict[str, Any]:
    if not QUOTE_CACHE_PATH.exists():
        return {}
    try:
        return json.loads(QUOTE_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed to load quote cache.")
        return {}


def _save_quote_cache(cache: dict[str, Any]) -> None:
    try:
        QUOTE_CACHE_PATH.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        logger.exception("Failed to save quote cache.")


def _build_cache_key(fund_code: str) -> str:
    return fund_code


def _is_cache_valid(cached_at: str | None) -> bool:
    cached_time = _parse_datetime(cached_at)
    if cached_time is None:
        return False
    return (_now_shanghai().replace(tzinfo=None) - cached_time).total_seconds() <= QUOTE_CACHE_TTL_SECONDS


def _should_use_quote_cache(now: datetime | None = None) -> bool:
    return _get_market_status(now) != "trading"


def _empty_result(fund_code: str, fund_name: str = "", message: str = "未获取到基金数据") -> dict[str, Any]:
    return {
        "fund_code": fund_code,
        "fund_name": fund_name,
        "display_nav": None,
        "display_nav_type": "unknown",
        "display_nav_label": "暂无数据",
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
        "status": "error",
        "message": message,
    }

def _require_akshare() -> None:
    if ak is None:
        raise RuntimeError("akshare 未安装，请先执行 `pip install -r requirements.txt`")


def _load_history_df(fund_code: str):
    _require_akshare()
    return ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")


def _build_history_payloads(history_df) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any]]:
    if history_df is None or history_df.empty:
        return None, None, {
            "daily_change_rate": None,
            "weekly_change_rate": None,
            "monthly_change_rate": None,
        }

    row = history_df.iloc[-1]
    nav = _safe_float(row.get("单位净值"))
    nav_date = _parse_date(row.get("净值日期"))
    official = None
    last_available = None

    if nav is not None:
        official = {
            "nav": nav,
            "nav_date": _format_date(nav_date),
            "is_latest_official": nav_date == _today(),
            "source": "akshare_history",
        }
        last_available = {
            "nav": nav,
            "nav_date": _format_date(nav_date),
            "source": "akshare_history",
        }

    closes = [_safe_float(value) for value in history_df["单位净值"].tolist()]
    closes = [value for value in closes if value is not None]

    def pct_change(days: int) -> float | None:
        if len(closes) <= days or closes[-days - 1] in (None, 0):
            return None
        previous = closes[-days - 1]
        current = closes[-1]
        if not previous:
            return None
        return round((current - previous) / previous * 100, 2)

    daily_change = _safe_float(row.get("日增长率"))
    trend = {
        "daily_change_rate": round(daily_change, 2) if daily_change is not None else None,
        "weekly_change_rate": pct_change(5),
        "monthly_change_rate": pct_change(22),
    }
    return official, last_available, trend


def _build_history_payloads_from_records(
    records: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any]]:
    if not records:
        return None, None, {
            "daily_change_rate": None,
            "weekly_change_rate": None,
            "monthly_change_rate": None,
        }

    closes = [_safe_float(item.get("close")) for item in records]
    closes = [value for value in closes if value is not None]
    if not closes:
        return None, None, {
            "daily_change_rate": None,
            "weekly_change_rate": None,
            "monthly_change_rate": None,
        }

    last_record = records[-1]
    nav = _safe_float(last_record.get("close"))
    nav_date = _parse_date(last_record.get("date"))
    official = None
    last_available = None
    if nav is not None:
        official = {
            "nav": nav,
            "nav_date": _format_date(nav_date),
            "is_latest_official": nav_date == _today(),
            "source": "eastmoney_history_records",
        }
        last_available = {
            "nav": nav,
            "nav_date": _format_date(nav_date),
            "source": "eastmoney_history_records",
        }

    def pct_change(days: int) -> float | None:
        if len(closes) <= days or closes[-days - 1] in (None, 0):
            return None
        previous = closes[-days - 1]
        current = closes[-1]
        if not previous:
            return None
        return round((current - previous) / previous * 100, 2)

    trend = {
        "daily_change_rate": pct_change(1),
        "weekly_change_rate": pct_change(5),
        "monthly_change_rate": pct_change(22),
    }
    return official, last_available, trend


def _load_preferred_history_payloads(
    fund_code: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any]]:
    fallback_trend = {
        "daily_change_rate": None,
        "weekly_change_rate": None,
        "monthly_change_rate": None,
    }

    records = _load_pingzhong_history_records(fund_code)
    if records:
        return _build_history_payloads_from_records(records)

    history_df = _load_history_df(fund_code)
    official, last_available, trend = _build_history_payloads(history_df)
    return official, last_available, trend or fallback_trend


def get_official_nav(fund_code: str) -> dict[str, Any] | None:
    """Get the latest official NAV available from free public data."""
    try:
        official, _, _ = _load_preferred_history_payloads(fund_code)
        return official
    except Exception:
        logger.exception("Failed to read official NAV history for fund %s.", fund_code)
        return None


def get_estimated_nav(fund_code: str) -> dict[str, Any] | None:
    """Get intraday estimated NAV from the public Eastmoney estimate endpoint."""
    url = ESTIMATE_URL_TEMPLATE.format(fund_code=fund_code)
    try:
        response = _http_get(
            url,
            params={"rt": int(datetime.now().timestamp() * 1000)},
            headers={"User-Agent": USER_AGENT},
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        content = response.text.strip()
        match = re.match(r"^jsonpgz\((.*)\);?$", content)
        if not match:
            return None
        payload = json.loads(match.group(1))
        return {
            "nav": _safe_float(payload.get("gsz")),
            "nav_time": _format_datetime(_parse_datetime(payload.get("gztime"))),
            "change_rate": _safe_float(payload.get("gszzl")),
            "official_nav": _safe_float(payload.get("dwjz")),
            "official_nav_date": _safe_str(payload.get("jzrq")) or None,
            "source": "eastmoney_estimate",
        }
    except Exception:
        logger.exception("Failed to read estimated NAV for fund %s.", fund_code)
        return None


def get_last_available_nav(fund_code: str) -> dict[str, Any] | None:
    """Get the most recent available official NAV from history."""
    try:
        _, last_available, _ = _load_preferred_history_payloads(fund_code)
        return last_available
    except Exception:
        logger.exception("Failed to read last available NAV for fund %s.", fund_code)
        return None


def get_trend_summary(fund_code: str) -> dict[str, Any]:
    """Build a small trend summary from free historical NAV data."""
    try:
        _, _, trend = _load_preferred_history_payloads(fund_code)
        return trend
    except Exception:
        logger.exception("Failed to build trend summary for fund %s.", fund_code)
        return {
            "daily_change_rate": None,
            "weekly_change_rate": None,
            "monthly_change_rate": None,
        }


def _load_pingzhong_history_records(fund_code: str) -> list[dict[str, Any]]:
    """Load full historical NAV records from Eastmoney pingzhongdata."""
    url = PINGZHONGDATA_URL_TEMPLATE.format(fund_code=fund_code)
    try:
        response = _http_get(
            url,
            params={"v": int(datetime.now().timestamp() * 1000)},
            headers={"User-Agent": USER_AGENT},
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        content = response.text
    except Exception:
        logger.exception("Failed to load pingzhong history for fund %s.", fund_code)
        return []

    match = re.search(r"Data_netWorthTrend\s*=\s*(\[.*?\]);", content, re.S)
    if not match:
        return []

    try:
        raw_items = json.loads(match.group(1))
    except json.JSONDecodeError:
        logger.exception("Failed to parse pingzhong history payload for fund %s.", fund_code)
        return []

    records: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        nav_date = _parse_timestamp_ms(item.get("x"))
        nav_value = _safe_float(item.get("y"))
        if nav_date is None or nav_value is None:
            continue
        records.append(
            {
                "date": nav_date.isoformat(),
                "open": nav_value,
                "close": nav_value,
                "high": nav_value,
                "low": nav_value,
            }
        )
    return records


def _load_history_records(fund_code: str) -> list[dict[str, Any]]:
    """Prefer full-history Eastmoney data, fallback to AkShare history."""
    records = _load_pingzhong_history_records(fund_code)
    if records:
        return records

    try:
        history_df = _load_history_df(fund_code)
    except Exception:
        logger.exception("Failed to load fallback history for %s.", fund_code)
        return []

    if history_df is None or history_df.empty:
        return []

    fallback_records: list[dict[str, Any]] = []
    for _, row in history_df.iterrows():
        nav_date = _format_date(_parse_date(row.get("净值日期")))
        nav_value = _safe_float(row.get("单位净值"))
        if not nav_date or nav_value is None:
            continue
        fallback_records.append(
            {
                "date": nav_date,
                "open": nav_value,
                "close": nav_value,
                "high": nav_value,
                "low": nav_value,
            }
        )
    return fallback_records


def _group_history_records(records: list[dict[str, Any]], normalized_period: str) -> list[dict[str, Any]]:
    if normalized_period == "day":
        return records

    grouped: dict[str, dict[str, Any]] = {}
    ordered_keys: list[str] = []
    for item in records:
        item_date = _parse_date(item.get("date"))
        if item_date is None:
            continue
        if normalized_period == "week":
            iso_year, iso_week, _ = item_date.isocalendar()
            group_key = f"{iso_year}-W{iso_week:02d}"
        else:
            group_key = item_date.strftime("%Y-%m")
        if group_key not in grouped:
            grouped[group_key] = item
            ordered_keys.append(group_key)
        else:
            grouped[group_key] = item

    return [grouped[key] for key in ordered_keys]


def get_fund_history(fund_code: str, period: str = "day", count: int = 60) -> list[dict[str, Any]]:
    """Return normalized history bars for one fund."""
    fund_code = _safe_str(fund_code)
    normalized_period = _safe_str(period).lower() or "day"
    if not fund_code:
        return []

    if normalized_period == "min":
        return []

    records = _load_history_records(fund_code)
    if not records:
        return []

    grouped_records = _group_history_records(records, normalized_period)
    return grouped_records[-max(count, 1) :]


def build_display_quote(
    fund_code: str,
    fund_name: str,
    official: dict[str, Any] | None,
    estimated: dict[str, Any] | None,
    last_available: dict[str, Any] | None,
    trend: dict[str, Any] | None,
) -> dict[str, Any]:
    """Apply the display priority: today's official NAV, else estimate, else latest NAV."""
    trend = trend or {}
    now = _now_shanghai()
    intraday_change = _build_intraday_change_payload(estimated=estimated, trend=trend)
    market_status = intraday_change.get("market_status")
    today_change = _build_today_change_payload(
        intraday_change,
        estimated=estimated,
        official=official,
        trend=trend,
        now=now,
    )
    today_change_time = _build_today_change_time_payload(
        today_change,
        estimated=estimated,
        official=official,
        last_available=last_available,
    )
    has_today_official = _has_same_day_official_update(official, estimated=estimated, now=now)
    latest_fallback = last_available if last_available and last_available.get("nav") is not None else (
        official if official and official.get("nav") is not None else None
    )
    primary_nav = _build_primary_nav_payload(
        market_status,
        official=official,
        estimated=estimated,
        last_available=latest_fallback,
        now=now,
    )

    display_nav = None
    display_nav_type = "unknown"
    display_nav_label = "暂无数据"
    is_estimated_used = False
    updated_at = None
    status = "partial"
    message = ""

    if official and official.get("nav") is not None and has_today_official:
        display_nav = official["nav"]
        display_nav_type = "official"
        display_nav_label = "正式净值"
        updated_at = official.get("nav_date")
        status = "ok"
        message = "当日正式净值已更新，已展示正式净值"
    elif market_status in {"pre_open", "non_trading_day"} and latest_fallback and latest_fallback.get("nav") is not None:
        display_nav = latest_fallback["nav"]
        display_nav_type = "last_available"
        display_nav_label = "最近净值"
        updated_at = latest_fallback.get("nav_date")
        status = "ok"
        message = "当前处于非交易时段，已展示最近一次正式净值"
    elif estimated and estimated.get("nav") is not None:
        display_nav = estimated["nav"]
        display_nav_type = "estimated"
        display_nav_label = "今日估值" if market_status == "closed" else "盘中估值"
        updated_at = estimated.get("nav_time")
        is_estimated_used = True
        status = "ok"
        message = "收盘后正式净值未更新，已展示今日估值" if market_status == "closed" else "当日正式净值未更新，已展示盘中估值"
    elif latest_fallback and latest_fallback.get("nav") is not None:
        display_nav = latest_fallback["nav"]
        display_nav_type = "last_available"
        display_nav_label = "最近净值"
        updated_at = latest_fallback.get("nav_date")
        status = "ok"
        message = "当日净值和估值不可用，已回退最近一次正式净值"
    else:
        status = "error"
        message = "未获取到正式净值、估值或最近净值"

    return {
        "fund_code": fund_code,
        "fund_name": fund_name,
        "display_nav": display_nav,
        "display_nav_type": display_nav_type,
        "display_nav_label": display_nav_label,
        "primary_nav_label": primary_nav.get("primary_nav_label"),
        "primary_nav_title": primary_nav.get("primary_nav_title"),
        "primary_nav_value": primary_nav.get("primary_nav_value"),
        "primary_nav_time_label": primary_nav.get("primary_nav_time_label"),
        "primary_nav_time_text": primary_nav.get("primary_nav_time_text"),
        "official_nav": official.get("nav") if official else None,
        "official_nav_date": official.get("nav_date") if official else None,
        "estimated_nav": estimated.get("nav") if estimated else None,
        "estimated_nav_time": estimated.get("nav_time") if estimated else None,
        "last_available_nav": latest_fallback.get("nav") if latest_fallback else None,
        "last_available_nav_date": latest_fallback.get("nav_date") if latest_fallback else None,
        "daily_change_rate": trend.get("daily_change_rate"),
        "weekly_change_rate": trend.get("weekly_change_rate"),
        "monthly_change_rate": trend.get("monthly_change_rate"),
        "intraday_change_rate": intraday_change.get("intraday_change_rate"),
        "intraday_change_text": intraday_change.get("intraday_change_text"),
        "intraday_change_label": intraday_change.get("intraday_change_label"),
        "today_change_rate": today_change.get("today_change_rate"),
        "today_change_text": today_change.get("today_change_text"),
        "today_change_label": today_change.get("today_change_label"),
        "today_change_time_label": today_change_time.get("today_change_time_label"),
        "today_change_time_text": today_change_time.get("today_change_time_text"),
        "market_status": market_status,
        "market_hint": _build_market_hint_payload(market_status).get("market_hint", ""),
        "is_estimated_used": is_estimated_used,
        "data_source": {
            "official": official.get("source") if official else None,
            "estimated": estimated.get("source") if estimated else None,
        },
        "updated_at": updated_at,
        "status": status,
        "message": message,
    }

def get_fund_quote(fund_code: str, fund_name: str = "") -> dict[str, Any]:
    """Query a single fund and normalize the result for UI and report use."""
    fund_code = _safe_str(fund_code)
    fund_name = _safe_str(fund_name)
    if not fund_code:
        return _empty_result(fund_code="", fund_name=fund_name, message="基金代码不能为空")

    cache = _load_quote_cache()
    cache_key = _build_cache_key(fund_code)
    cached_entry = cache.get(cache_key)
    if _should_use_quote_cache() and isinstance(cached_entry, dict) and _is_cache_valid(cached_entry.get("cached_at")):
        cached_result = _hydrate_today_change_fields(cached_entry.get("result", {}))
        if cached_result:
            if fund_name and not cached_result.get("fund_name"):
                cached_result["fund_name"] = fund_name
            cached_result["message"] = "已命中本地缓存"
            return cached_result

    try:
        estimated = get_estimated_nav(fund_code)
        official = None
        last_available = None
        trend = {
            "daily_change_rate": None,
            "weekly_change_rate": None,
            "monthly_change_rate": None,
        }
        try:
            official, last_available, trend = _load_preferred_history_payloads(fund_code)
        except Exception:
            logger.exception("Failed to load history payloads for %s, fallback to estimate-first quote.", fund_code)
            fallback_records = _load_history_records(fund_code)
            if fallback_records:
                official, last_available, trend = _build_history_payloads_from_records(fallback_records)
        if (not official or official.get("nav") is None) and estimated:
            estimated_official_nav = estimated.get("official_nav")
            estimated_official_date = estimated.get("official_nav_date")
            if estimated_official_nav is not None:
                official = {
                    "nav": estimated_official_nav,
                    "nav_date": estimated_official_date,
                    "is_latest_official": _parse_date(estimated_official_date) == _today(),
                    "source": "eastmoney_estimate_embedded_official",
                }
            if last_available is None and estimated_official_nav is not None:
                last_available = {
                    "nav": estimated_official_nav,
                    "nav_date": estimated_official_date,
                    "source": "eastmoney_estimate_embedded_official",
                }
        result = build_display_quote(
            fund_code=fund_code,
            fund_name=fund_name,
            official=official,
            estimated=estimated,
            last_available=last_available,
            trend=trend,
        )
        result = _hydrate_today_change_fields(result)
        if not result.get("fund_name"):
            result["fund_name"] = fund_name
        cache[cache_key] = {
            "cached_at": _format_datetime(_now_shanghai().replace(tzinfo=None)),
            "result": result,
        }
        _save_quote_cache(cache)
        return result
    except Exception as exc:
        logger.exception("Failed to build normalized fund quote for %s.", fund_code)
        return _empty_result(fund_code=fund_code, fund_name=fund_name, message=str(exc))
