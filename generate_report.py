"""Generate local Word-compatible reports for fund market analysis."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
import tempfile

from app_logging import get_logger
from analyze_fund import analyze_news
from fetch_news import fetch_news
from portfolio import (
    build_portfolio_summary,
    load_portfolio,
    load_users,
    normalize_single_user_portfolio,
)
from report_export import export_report_to_doc
from send_email import send_report_email, send_report_email_to


TEMP_REPORTS_DIR = Path(tempfile.gettempdir()) / "fund_analysis_reports"
logger = get_logger("generate_report")


def build_news_text(items: list[str]) -> str:
    if not items:
        return "暂无新闻数据，请先检查抓取逻辑或网络连接。"
    return "\n".join(items)


def _safe_name(value: str) -> str:
    cleaned = "".join(char for char in value if char not in '<>:"/\\|?*').strip()
    return cleaned or "未命名用户"


def _next_user_report_filename(owner: str) -> str:
    now = datetime.now()
    safe_owner = _safe_name(owner)
    prefix = now.strftime(f"%Y年%m月%d日_%H时%M分%S秒_{safe_owner}_报告")
    existing_numbers: list[int] = []

    TEMP_REPORTS_DIR.mkdir(exist_ok=True)
    for path in TEMP_REPORTS_DIR.glob(f"{prefix}*.doc"):
        match = re.search(r"_报告(\d+)\.doc$", path.name)
        if match:
            existing_numbers.append(int(match.group(1)))

    next_number = max(existing_numbers, default=0) + 1
    return f"{prefix}{next_number:02d}.doc"


def _build_users_to_process() -> list[dict]:
    users = load_users()
    if users:
        return users
    return [normalize_single_user_portfolio(load_portfolio())]


def _generate_one_user_report(user: dict, news_text: str) -> tuple[Path, str, str]:
    owner = user.get("owner", "默认用户")
    portfolio_text = build_portfolio_summary(user)
    report_content = analyze_news(news_text, portfolio_text=portfolio_text)
    report_content += "\n\n---\n\n## 当前持仓输入\n\n" + portfolio_text
    report_content += "\n\n---\n\n## 原始新闻输入\n\n" + news_text

    filename = _next_user_report_filename(owner)
    report_path = TEMP_REPORTS_DIR / filename
    export_report_to_doc("支付宝基金日报分析", report_content, report_path)
    return report_path, report_content, owner


def main() -> None:
    logger.info("Report generation started.")

    try:
        news_items = fetch_news()
        logger.info("Fetched %s news items.", len(news_items))
        news_text = build_news_text(news_items)
        users = _build_users_to_process()
        logger.info("Processing %s user(s).", len(users))

        for user in users:
            owner = user.get("owner", "默认用户")
            recipients = user.get("email_to", [])
            logger.info("Generating report for user: %s", owner)

            report_path, report_content, owner = _generate_one_user_report(user, news_text)
            logger.info("Temporary report generated for %s: %s", owner, report_path)

            try:
                if recipients:
                    email_result = send_report_email_to(
                        report_path=report_path,
                        report_content=report_content,
                        recipients=recipients,
                        owner=owner,
                    )
                else:
                    email_result = send_report_email(report_path, report_content)
                logger.info(email_result)
                print(email_result)
            finally:
                if report_path.exists():
                    report_path.unlink()
                    logger.info("Temporary report removed for %s: %s", owner, report_path)
    except Exception:
        logger.exception("Report generation failed unexpectedly.")
        raise


if __name__ == "__main__":
    main()
