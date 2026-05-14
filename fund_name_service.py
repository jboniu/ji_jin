"""Resolve fund codes from fund names using local data first, then public search."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

import requests

from app_logging import get_logger
from portfolio import load_users


FUND_SEARCH_URL = "https://fund.eastmoney.com/js/fundcode_search.js"
FUND_NAME_CACHE_PATH = Path("fund_name_cache.json")
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/135.0.0.0 Safari/537.36"
)
DEFAULT_TIMEOUT = 10

logger = get_logger("fund_name_service")


def _safe_str(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _normalize_name(value: str) -> str:
    text = _safe_str(value)
    text = text.replace("（", "(").replace("）", ")")
    text = re.sub(r"\s+", "", text)
    return text.lower()


def _is_valid_code(value: Any) -> bool:
    return bool(re.fullmatch(r"\d{6}", _safe_str(value)))


def _load_cache() -> dict[str, str]:
    if not FUND_NAME_CACHE_PATH.exists():
        return {}
    try:
        data = json.loads(FUND_NAME_CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception("Failed to load fund name cache.")
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items()}


def _save_cache(cache: dict[str, str]) -> None:
    try:
        FUND_NAME_CACHE_PATH.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        logger.exception("Failed to save fund name cache.")


def _collect_local_candidates() -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    users = load_users()
    for user in users:
        for position in user.get("positions", []):
            fund_name = _safe_str(position.get("fund_name"))
            fund_code = _safe_str(position.get("fund_code"))
            if fund_name and _is_valid_code(fund_code):
                candidates.append((fund_name, fund_code))
    return candidates


def _resolve_from_local(fund_name: str) -> str:
    normalized_target = _normalize_name(fund_name)
    if not normalized_target:
        return ""

    for candidate_name, candidate_code in _collect_local_candidates():
        normalized_candidate = _normalize_name(candidate_name)
        if normalized_candidate == normalized_target:
            return candidate_code

    for candidate_name, candidate_code in _collect_local_candidates():
        normalized_candidate = _normalize_name(candidate_name)
        if normalized_target and normalized_target in normalized_candidate:
            return candidate_code
        if normalized_candidate and normalized_candidate in normalized_target:
            return candidate_code
    return ""


def _parse_remote_search_payload(text: str) -> list[list[Any]]:
    match = re.search(r"\[\s*\[.*\]\s*\]", text, re.S)
    if not match:
        return []
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, list)]


def _resolve_from_remote(fund_name: str) -> str:
    try:
        session = requests.Session()
        session.trust_env = False
        response = session.get(
            FUND_SEARCH_URL,
            headers={"User-Agent": USER_AGENT},
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
    except Exception:
        logger.exception("Failed to fetch remote fund name search data.")
        return ""

    normalized_target = _normalize_name(fund_name)
    if not normalized_target:
        return ""

    payload = _parse_remote_search_payload(response.text)
    exact_matches: list[str] = []
    fuzzy_matches: list[str] = []

    for item in payload:
        if len(item) < 3:
            continue
        candidate_code = _safe_str(item[0])
        candidate_name = _safe_str(item[2])
        if not _is_valid_code(candidate_code) or not candidate_name:
            continue
        normalized_candidate = _normalize_name(candidate_name)
        if normalized_candidate == normalized_target:
            exact_matches.append(candidate_code)
            continue
        if normalized_target in normalized_candidate or normalized_candidate in normalized_target:
            fuzzy_matches.append(candidate_code)

    if exact_matches:
        return exact_matches[0]
    if fuzzy_matches:
        return fuzzy_matches[0]
    return ""


def resolve_fund_code_by_name(fund_name: str) -> str:
    """Resolve one fund code from a fund name."""
    normalized_name = _normalize_name(fund_name)
    if not normalized_name:
        return ""

    cache = _load_cache()
    cached = _safe_str(cache.get(normalized_name))
    if _is_valid_code(cached):
        return cached

    local_code = _resolve_from_local(fund_name)
    if _is_valid_code(local_code):
        cache[normalized_name] = local_code
        _save_cache(cache)
        return local_code

    remote_code = _resolve_from_remote(fund_name)
    if _is_valid_code(remote_code):
        cache[normalized_name] = remote_code
        _save_cache(cache)
        return remote_code
    return ""


def resolve_preferred_fund_code(fund_name: str, current_code: str = "") -> str:
    """Prefer resolving by fund name first, then fall back to the current valid code."""
    resolved_code = resolve_fund_code_by_name(fund_name)
    if _is_valid_code(resolved_code):
        return resolved_code

    normalized_current = _safe_str(current_code)
    if _is_valid_code(normalized_current):
        return normalized_current
    return ""
