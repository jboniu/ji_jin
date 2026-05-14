"""Service helpers for generating user reports through the API."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
import uuid
from typing import Any

from analyze_fund import analyze_news
from app_logging import get_logger
from database import is_data_backend_strict
from db_report_repository import is_db_report_repository_available, upsert_report_index_item
from db_task_repository import (
    is_db_task_repository_available,
    load_report_task,
    upsert_report_task,
)
from fetch_news import fetch_news
from generate_report import build_news_text
from portfolio import build_portfolio_summary
from report_export import export_report_to_doc
from send_email import send_report_email_to
from storage_service import is_storage_backend_strict, upload_bytes_to_reports_storage
from user_service import get_user_by_id


REPORTS_DIR = Path("reports")
REPORT_INDEX_PATH = Path("report_index.json")
REPORT_TASKS_PATH = Path("report_tasks.json")
logger = get_logger("report_service")
REPORT_TASKS: dict[str, dict[str, Any]] = {}


def _load_report_tasks() -> dict[str, dict[str, Any]]:
    if not REPORT_TASKS_PATH.exists():
        return {}
    try:
        data = json.loads(REPORT_TASKS_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        logger.exception("Failed to load report tasks cache.")
        return {}


def _save_report_tasks() -> None:
    try:
        REPORT_TASKS_PATH.write_text(
            json.dumps(REPORT_TASKS, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        logger.exception("Failed to save report tasks cache.")


def _load_report_index() -> list[dict[str, Any]]:
    if not REPORT_INDEX_PATH.exists():
        return []
    try:
        data = json.loads(REPORT_INDEX_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        logger.exception("Failed to load report index.")
        return []


def _save_report_index(items: list[dict[str, Any]]) -> None:
    try:
        REPORT_INDEX_PATH.write_text(
            json.dumps(items, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        logger.exception("Failed to save report index.")


def _append_report_index(
    user_id: str,
    owner: str,
    report_path: Path,
    stored_path: str | None = None,
) -> None:
    item = {
        "report_id": report_path.name,
        "file_name": report_path.name,
        "file_type": report_path.suffix.lower().lstrip("."),
        "owner": owner,
        "user_id": user_id,
        "updated_at": report_path.stat().st_mtime,
        "path": stored_path or str(report_path.resolve()),
    }
    items = _load_report_index()
    items.insert(0, item)
    _save_report_index(items)
    if is_db_report_repository_available():
        try:
            upsert_report_index_item(item)
        except Exception:
            logger.exception(
                "Failed to persist report index item to database: %s",
                report_path.name,
            )


def _safe_name(value: str) -> str:
    cleaned = "".join(char for char in value if char not in '<>:"/\\|?*').strip()
    return cleaned or "未命名用户"


def _next_report_filename(owner: str) -> str:
    now = datetime.now()
    safe_owner = _safe_name(owner)
    prefix = now.strftime(f"%Y年%m月%d日_%H时%M分%S秒_{safe_owner}_报告")
    existing_numbers: list[int] = []

    REPORTS_DIR.mkdir(exist_ok=True)
    for path in REPORTS_DIR.glob(f"{prefix}*.doc"):
        match = re.search(r"_报告(\d+)\.doc$", path.name)
        if match:
            existing_numbers.append(int(match.group(1)))

    next_number = max(existing_numbers, default=0) + 1
    return f"{prefix}{next_number:02d}.doc"


def _build_report_content(user: dict[str, Any], news_text: str) -> str:
    portfolio_text = build_portfolio_summary(user)
    report_content = analyze_news(news_text, portfolio_text=portfolio_text)
    report_content += "\n\n---\n\n## 当前持仓输入\n\n" + portfolio_text
    report_content += "\n\n---\n\n## 原始新闻输入\n\n" + news_text
    return report_content


def _store_report_file(report_path: Path) -> dict[str, str]:
    """Persist one generated report, preferring Supabase and keeping local fallback."""
    report_bytes = report_path.read_bytes()
    try:
        stored = upload_bytes_to_reports_storage(
            file_name=report_path.name,
            content=report_bytes,
            content_type="application/msword",
        )
        return {
            "storage_backend": stored.get("backend", "supabase"),
            "stored_path": stored.get("stored_path", str(report_path.resolve())),
            "stored_file_name": stored.get("stored_file_name", report_path.name),
        }
    except Exception:
        if is_storage_backend_strict():
            raise
        logger.exception(
            "Failed to upload report to Supabase Storage, falling back to local path: %s",
            report_path,
        )
        return {
            "storage_backend": "local",
            "stored_path": str(report_path.resolve()),
            "stored_file_name": report_path.name,
        }


def generate_report_for_user(user_id: str, send_email: bool | None = None) -> dict[str, Any] | None:
    """Generate one user's report and optionally send it by email."""
    user = get_user_by_id(user_id)
    if user is None:
        return None

    owner = user.get("owner", "默认用户")
    recipients = user.get("email_to", [])
    should_send_email = bool(user.get("subscribe_email_reports", False)) if send_email is None else bool(send_email)

    logger.info("Starting report generation for user_id=%s owner=%s", user_id, owner)
    news_items = fetch_news()
    news_text = build_news_text(news_items)
    report_content = _build_report_content(user, news_text)

    filename = _next_report_filename(owner)
    report_path = REPORTS_DIR / filename
    export_report_to_doc("基金日报分析", report_content, report_path)
    storage_meta = _store_report_file(report_path)
    _append_report_index(
        user_id=user_id,
        owner=owner,
        report_path=report_path,
        stored_path=storage_meta.get("stored_path"),
    )
    logger.info("Report generated for user_id=%s path=%s", user_id, report_path)

    email_result = "Email skipped."
    if should_send_email and recipients:
        email_result = send_report_email_to(
            report_path=report_path,
            report_content=report_content,
            recipients=recipients,
            owner=owner,
        )
        logger.info("Email result for user_id=%s: %s", user_id, email_result)
    elif should_send_email and not recipients:
        email_result = "Email skipped because the user has no recipients configured."

    return {
        "user_id": user_id,
        "owner": owner,
        "report_file_name": report_path.name,
        "report_path": str(report_path.resolve()),
        "storage_backend": storage_meta.get("storage_backend", "local"),
        "stored_path": storage_meta.get("stored_path", str(report_path.resolve())),
        "report_content": report_content,
        "email_result": email_result,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def create_report_task(user_id: str, send_email: bool | None = None) -> dict[str, Any] | None:
    """Create an async-style task record for report generation."""
    user = get_user_by_id(user_id)
    if user is None:
        return None

    task_id = uuid.uuid4().hex
    owner = user.get("owner", "默认用户")
    task = {
        "task_id": task_id,
        "user_id": user_id,
        "owner": owner,
        "status": "pending",
        "message": "任务已创建，等待生成",
        "send_email": send_email,
        "result": None,
        "error": "",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    REPORT_TASKS[task_id] = task
    if is_db_task_repository_available():
        try:
            persisted = upsert_report_task(task)
            REPORT_TASKS[task_id] = persisted
            return persisted
        except Exception:
            if is_data_backend_strict():
                raise
            logger.exception("Failed to persist report task to database: %s", task_id)
    _save_report_tasks()
    return REPORT_TASKS[task_id]


def run_report_task(task_id: str) -> None:
    """Execute one queued report task and update its status."""
    task = REPORT_TASKS.get(task_id)
    if task is None:
        return

    task["status"] = "running"
    task["message"] = "报告生成中"
    task["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if is_db_task_repository_available():
        try:
            task = upsert_report_task(task)
            REPORT_TASKS[task_id] = task
        except Exception:
            if is_data_backend_strict():
                raise
            logger.exception("Failed to update running report task in database: %s", task_id)
            _save_report_tasks()
    else:
        _save_report_tasks()

    try:
        result = generate_report_for_user(
            user_id=task["user_id"],
            send_email=task.get("send_email"),
        )
        if result is None:
            task["status"] = "failed"
            task["message"] = "用户不存在"
            task["error"] = "User not found"
        else:
            task["status"] = "completed"
            task["message"] = "报告生成完成"
            task["result"] = result
    except Exception as exc:
        logger.exception("Async report task failed: %s", task_id)
        task["status"] = "failed"
        task["message"] = "报告生成失败"
        task["error"] = str(exc)

    task["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if is_db_task_repository_available():
        try:
            task = upsert_report_task(task)
            REPORT_TASKS[task_id] = task
        except Exception:
            if is_data_backend_strict():
                raise
            logger.exception("Failed to finalize report task in database: %s", task_id)
            _save_report_tasks()
    else:
        _save_report_tasks()


def get_report_task(task_id: str) -> dict[str, Any] | None:
    """Return one async report task snapshot."""
    if is_db_task_repository_available():
        try:
            task = load_report_task(task_id)
            if task is not None:
                REPORT_TASKS[task_id] = task
                return task
        except Exception:
            if is_data_backend_strict():
                raise
            logger.exception("Failed to load report task from database: %s", task_id)
    return REPORT_TASKS.get(task_id)


REPORT_TASKS.update(_load_report_tasks())
