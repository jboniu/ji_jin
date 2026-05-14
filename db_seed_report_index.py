"""Import local report_index.json into PostgreSQL."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from database import get_database_url
from db_report_repository import upsert_report_index_item


REPORT_INDEX_PATH = Path("report_index.json")


def _load_report_index(path: Path = REPORT_INDEX_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def seed_report_index() -> dict[str, int]:
    """Insert local report index items into PostgreSQL."""
    database_url = get_database_url()
    if not database_url:
        raise RuntimeError("DATABASE_URL 未配置，无法导入报告索引数据")

    items = _load_report_index()
    seeded_count = 0

    for item in items:
        if not isinstance(item, dict):
            continue
        payload = {
            "report_id": str(item.get("report_id", "")).strip(),
            "user_id": str(item.get("user_id", "")).strip(),
            "owner": str(item.get("owner", "")).strip(),
            "file_name": str(item.get("file_name", "")).strip(),
            "file_type": str(item.get("file_type", "")).strip(),
            "path": str(item.get("path", "")).strip(),
        }
        if not payload["report_id"] or not payload["user_id"]:
            continue
        upsert_report_index_item(payload)
        seeded_count += 1

    return {
        "report_index_items": seeded_count,
    }


if __name__ == "__main__":
    result = seed_report_index()
    print(f"seeded_report_index_items={result['report_index_items']}")
