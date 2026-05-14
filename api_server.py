"""HTTP API server for the fund report mini-program backend."""

from __future__ import annotations

from datetime import datetime
import re

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile

from auth_service import authenticate_user, change_user_password
from database import get_database_health, is_data_backend_strict
from fund_quote import get_fund_history
from fund_quote_service import (
    build_fallback_quote_payload,
    get_quote_payload,
    get_user_quote_trends_payload,
    get_user_quotes_payload,
)
from position_import_service import recognize_positions_from_image
from report_repository import get_report_detail_for_user, list_reports_for_user
from report_service import create_report_task, generate_report_for_user, get_report_task, run_report_task
from storage_service import get_storage_health, is_storage_backend_strict
from upload_service import create_import_task, get_import_task, update_import_task
from user_service import (
    add_user_position,
    build_user_summary,
    delete_user_position,
    get_all_users,
    get_user_by_id,
    get_user_positions,
    merge_imported_positions,
    update_user_position,
    update_user_profile,
)


app = FastAPI(
    title="Fund Report Mini Program API",
    version="0.1.0",
    description="Backend API for personalized fund report generation and fund quote lookup.",
)

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _strict_mode_http_error(exc: Exception, fallback_detail: str) -> HTTPException:
    message = str(exc).strip() or fallback_detail
    return HTTPException(status_code=503, detail=message)


@app.get("/api/health")
def health_check() -> dict:
    """Return a simple health payload for local verification."""
    database = get_database_health()
    storage = get_storage_health()
    return {
        "status": "ok",
        "service": "fund-report-api",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data_backend": database.get("mode", "json"),
        "database": database,
        "storage_backend": storage.get("mode", "local"),
        "storage": storage,
        "strict_mode": {
            "data_backend_strict": is_data_backend_strict(),
            "storage_backend_strict": is_storage_backend_strict(),
        },
    }


@app.post("/api/auth/login")
def login(payload: dict) -> dict:
    """Authenticate one local user and return a simple session payload."""
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    if not username or not password:
        raise HTTPException(status_code=400, detail="username and password are required")

    try:
        session = authenticate_user(username=username, password=password)
    except Exception as exc:
        raise _strict_mode_http_error(exc, "Authentication backend is unavailable") from exc
    if session is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return session


@app.post("/api/users/{user_id}/change-password")
def change_password(user_id: str, payload: dict) -> dict:
    """Change one user's password after verifying the old password."""
    old_password = str(payload.get("old_password", ""))
    new_password = str(payload.get("new_password", ""))
    try:
        result = change_user_password(
            user_id=user_id,
            old_password=old_password,
            new_password=new_password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise _strict_mode_http_error(exc, "Authentication backend is unavailable") from exc

    if result is None:
        raise HTTPException(status_code=404, detail="User not found")
    return result


@app.get("/api/users")
def list_users() -> dict:
    """List all configured users."""
    users = get_all_users()
    return {
        "items": [build_user_summary(user) for user in users],
        "total": len(users),
    }


@app.get("/api/users/{user_id}")
def get_user(user_id: str) -> dict:
    """Return one user profile by id."""
    user = get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.put("/api/users/{user_id}")
def update_user(user_id: str, payload: dict) -> dict:
    """Update one user's profile fields."""
    owner = str(payload.get("owner", "")).strip()
    if not owner:
        raise HTTPException(status_code=400, detail="Owner is required")

    email_to = payload.get("email_to", [])
    if not isinstance(email_to, list):
        raise HTTPException(status_code=400, detail="email_to must be a list")
    invalid_emails = [item for item in email_to if not EMAIL_PATTERN.match(str(item).strip())]
    if invalid_emails:
        raise HTTPException(status_code=400, detail=f"Invalid email(s): {', '.join(map(str, invalid_emails))}")
    subscribe_email_reports = bool(payload.get("subscribe_email_reports", False))

    user = update_user_profile(
        user_id=user_id,
        owner=owner,
        email_to=email_to,
        subscribe_email_reports=subscribe_email_reports,
    )
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.get("/api/users/{user_id}/positions")
def list_user_positions(user_id: str) -> dict:
    """Return one user's positions."""
    positions = get_user_positions(user_id)
    if positions is None:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "user_id": user_id,
        "items": positions,
        "total": len(positions),
    }


@app.post("/api/users/{user_id}/positions/import-image")
async def import_positions_image(user_id: str, file: UploadFile = File(...)) -> dict:
    """Upload one screenshot image and recognize positions for confirmation."""
    user = get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    filename = str(file.filename or "").strip()
    if not filename:
        raise HTTPException(status_code=400, detail="file name is required")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="file is empty")

    content_type = str(file.content_type or "").strip() or "image/png"
    try:
        task = create_import_task(
            user_id=user_id,
            filename=filename,
            content=content,
            content_type=content_type,
        )
    except Exception as exc:
        raise _strict_mode_http_error(exc, "Storage backend is unavailable") from exc
    update_import_task(task["task_id"], status="recognizing", message="截图上传成功，正在识别基金持仓")

    try:
        positions = recognize_positions_from_image(
            image_bytes=content,
            mime_type=content_type,
        )
    except Exception as exc:
        update_import_task(
            task["task_id"],
            status="failed",
            message=f"识别失败：{exc}",
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail=f"识别失败：{exc}") from exc

    completed_task = update_import_task(
        task["task_id"],
        status="pending_confirmation",
        message=f"已识别 {len(positions)} 条持仓，请确认后导入",
        recognized_positions=positions,
        imported_count=len(positions),
    )
    return completed_task or task


@app.get("/api/users/{user_id}/positions/import-tasks/{task_id}")
def get_positions_import_task(user_id: str, task_id: str) -> dict:
    """Get one screenshot import task snapshot."""
    task = get_import_task(task_id)
    if task is None or task.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Import task not found")
    return task


@app.post("/api/users/{user_id}/positions/import-tasks/{task_id}/confirm")
def confirm_positions_import_task(user_id: str, task_id: str) -> dict:
    """Confirm one recognized import task and merge it into holdings."""
    task = get_import_task(task_id)
    if task is None or task.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Import task not found")

    positions = task.get("recognized_positions") or []
    if not isinstance(positions, list) or not positions:
        raise HTTPException(status_code=400, detail="No recognized positions to import")

    try:
        merge_result = merge_imported_positions(user_id=user_id, positions=positions)
    except Exception as exc:
        raise _strict_mode_http_error(exc, "Data backend is unavailable") from exc
    if merge_result is None:
        raise HTTPException(status_code=404, detail="User not found")

    updated_task = update_import_task(
        task_id,
        status="completed",
        message=f"已更新 {merge_result['updated_count']} 条，新增 {merge_result['created_count']} 条持仓",
        created_count=merge_result["created_count"],
        updated_count=merge_result["updated_count"],
    )
    return updated_task or task


@app.post("/api/users/{user_id}/positions")
def create_user_position(user_id: str, payload: dict) -> dict:
    """Create one position for a user."""
    fund_code = str(payload.get("fund_code", "")).strip()
    fund_name = str(payload.get("fund_name", "")).strip()
    if not fund_code or not fund_name:
        raise HTTPException(status_code=400, detail="fund_code and fund_name are required")
    if len(fund_code) < 4 or len(fund_code) > 10:
        raise HTTPException(status_code=400, detail="fund_code length is invalid")

    try:
        holding_amount = float(payload.get("holding_amount", 0) or 0)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="holding_amount must be a number")
    if holding_amount < 0:
        raise HTTPException(status_code=400, detail="holding_amount cannot be negative")

    position = {
        "fund_code": fund_code,
        "fund_name": fund_name,
        "category": str(payload.get("category", "")).strip(),
        "holding_amount": round(holding_amount, 2),
        "note": str(payload.get("note", "")).strip(),
    }
    user = add_user_position(user_id, position)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.put("/api/users/{user_id}/positions/{fund_code}")
def edit_user_position(user_id: str, fund_code: str, payload: dict) -> dict:
    """Update one position for a user."""
    next_fund_code = str(payload.get("fund_code", fund_code)).strip() or fund_code
    fund_name = str(payload.get("fund_name", "")).strip()
    if len(next_fund_code) < 4 or len(next_fund_code) > 10:
        raise HTTPException(status_code=400, detail="fund_code length is invalid")
    if not fund_name:
        raise HTTPException(status_code=400, detail="fund_name is required")

    try:
        holding_amount = float(payload.get("holding_amount", 0) or 0)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="holding_amount must be a number")
    if holding_amount < 0:
        raise HTTPException(status_code=400, detail="holding_amount cannot be negative")

    updated = {
        "fund_code": next_fund_code,
        "fund_name": fund_name,
        "category": str(payload.get("category", "")).strip(),
        "holding_amount": round(holding_amount, 2),
        "note": str(payload.get("note", "")).strip(),
    }
    user = update_user_position(user_id, fund_code, updated)
    if user is None:
        raise HTTPException(status_code=404, detail="Position not found")
    return user


@app.delete("/api/users/{user_id}/positions/{fund_code}")
def remove_user_position(user_id: str, fund_code: str) -> dict:
    """Delete one position for a user."""
    user = delete_user_position(user_id, fund_code)
    if user is None:
        raise HTTPException(status_code=404, detail="Position not found")
    return user


@app.get("/api/funds/{fund_code}/quote")
def get_fund_quote_api(fund_code: str, fund_name: str = "") -> dict:
    """Return a single fund quote payload for UI display."""
    result = get_quote_payload(fund_code=fund_code, fund_name=fund_name)
    if result.get("status") == "error":
        return build_fallback_quote_payload(
            fund_code=fund_code,
            fund_name=fund_name,
            message="该基金暂时无法拉取行情，当前仅展示本地持仓信息",
        )
    return result


@app.get("/api/funds/lookup")
def lookup_fund_quote_api(fund_name: str, fund_code: str = "") -> dict:
    """Return a single fund quote payload, preferring fund-name resolution."""
    result = get_quote_payload(fund_code=fund_code, fund_name=fund_name)
    if result.get("status") == "error":
        return build_fallback_quote_payload(
            fund_code=fund_code,
            fund_name=fund_name,
            message="该基金暂时无法拉取行情，当前仅展示本地持仓信息",
        )
    return result


@app.get("/api/funds/{fund_code}/history")
def get_fund_history_api(fund_code: str, period: str = "day", count: int = 60) -> dict:
    """Return one fund's normalized history series for chart rendering."""
    normalized_period = str(period or "day").strip().lower()
    if normalized_period not in {"day", "week", "month", "min"}:
        raise HTTPException(status_code=400, detail="period must be one of: day, week, month, min")
    if count <= 0 or count > 300:
        raise HTTPException(status_code=400, detail="count must be between 1 and 300")

    items = get_fund_history(fund_code=fund_code, period=normalized_period, count=count)
    return {
        "fund_code": fund_code,
        "period": normalized_period,
        "items": items,
        "total": len(items),
    }


@app.get("/api/users/{user_id}/quotes")
def list_user_quotes(user_id: str) -> dict:
    """Return all normalized fund quote items for one user."""
    result = get_user_quotes_payload(user_id)
    if result is None:
        raise HTTPException(status_code=404, detail="User not found")
    return result


@app.get("/api/users/{user_id}/quote-trends")
def list_user_quote_trends(user_id: str, period: str = "week", count: int = 8) -> dict:
    """Return lightweight history previews for one user's funds."""
    normalized_period = str(period or "week").strip().lower()
    if normalized_period not in {"day", "week", "month"}:
        raise HTTPException(status_code=400, detail="period must be one of: day, week, month")
    if count <= 0 or count > 60:
        raise HTTPException(status_code=400, detail="count must be between 1 and 60")

    result = get_user_quote_trends_payload(user_id=user_id, period=normalized_period, count=count)
    if result is None:
        raise HTTPException(status_code=404, detail="User not found")
    return result


@app.post("/api/users/{user_id}/reports/generate")
def generate_user_report(user_id: str, payload: dict | None = None) -> dict:
    """Generate one user's report immediately."""
    send_email = None if payload is None else payload.get("send_email")
    if send_email is not None:
        send_email = bool(send_email)
    try:
        result = generate_report_for_user(user_id=user_id, send_email=send_email)
    except Exception as exc:
        raise _strict_mode_http_error(exc, "Report generation backend is unavailable") from exc
    if result is None:
        raise HTTPException(status_code=404, detail="User not found")
    return result


@app.post("/api/users/{user_id}/reports/tasks")
def create_user_report_task(user_id: str, background_tasks: BackgroundTasks, payload: dict | None = None) -> dict:
    """Create a background report generation task and return immediately."""
    send_email = None if payload is None else payload.get("send_email")
    if send_email is not None:
        send_email = bool(send_email)
    try:
        task = create_report_task(user_id=user_id, send_email=send_email)
    except Exception as exc:
        raise _strict_mode_http_error(exc, "Report task backend is unavailable") from exc
    if task is None:
        raise HTTPException(status_code=404, detail="User not found")
    background_tasks.add_task(run_report_task, task["task_id"])
    return task


@app.get("/api/users/{user_id}/reports/tasks/{task_id}")
def get_user_report_task(user_id: str, task_id: str) -> dict:
    """Get one report task status snapshot."""
    try:
        task = get_report_task(task_id)
    except Exception as exc:
        raise _strict_mode_http_error(exc, "Report task backend is unavailable") from exc
    if task is None or task.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.get("/api/users/{user_id}/reports")
def list_user_reports(user_id: str) -> dict:
    """List one user's report history."""
    try:
        result = list_reports_for_user(user_id)
    except Exception as exc:
        raise _strict_mode_http_error(exc, "Report repository is unavailable") from exc
    if result is None:
        raise HTTPException(status_code=404, detail="User not found")
    return result


@app.get("/api/users/{user_id}/reports/{report_id}")
def get_user_report_detail(user_id: str, report_id: str) -> dict:
    """Return one report detail for the specified user."""
    try:
        result = get_report_detail_for_user(user_id, report_id)
    except Exception as exc:
        raise _strict_mode_http_error(exc, "Report content backend is unavailable") from exc
    if result is None:
        raise HTTPException(status_code=404, detail="User not found")
    if not result:
        raise HTTPException(status_code=404, detail="Report not found")
    return result
