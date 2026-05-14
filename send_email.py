"""Send generated reports by email using SMTP."""

from __future__ import annotations

import os
import smtplib
import time
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv

from app_logging import get_logger


MAX_EMAIL_RETRIES = 2
logger = get_logger("send_email")


def _is_enabled(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _load_email_config() -> dict[str, str]:
    load_dotenv()
    return {
        "host": os.getenv("SMTP_HOST", "").strip(),
        "port": os.getenv("SMTP_PORT", "465").strip(),
        "username": os.getenv("SMTP_USERNAME", "").strip(),
        "password": os.getenv("SMTP_PASSWORD", "").strip(),
        "use_ssl": os.getenv("SMTP_USE_SSL", "true").strip(),
        "from_addr": os.getenv("EMAIL_FROM", "").strip(),
        "to_addr": os.getenv("EMAIL_TO", "").strip(),
    }


def _parse_recipients(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _validate_config(config: dict[str, str]) -> tuple[bool, str]:
    required = ["host", "port", "username", "password", "from_addr", "to_addr"]
    missing = [key for key in required if not config[key]]
    if missing:
        return False, f"邮箱未发送：缺少配置 {', '.join(missing)}"
    if not _parse_recipients(config["to_addr"]):
        return False, "邮箱未发送：EMAIL_TO 中没有有效收件人"
    return True, ""


def _build_email_message(
    from_addr: str,
    recipients: list[str],
    subject: str,
    body_text: str,
    attachment_path: Path,
) -> EmailMessage:
    email = EmailMessage()
    email["Subject"] = subject
    email["From"] = from_addr
    email["To"] = ", ".join(recipients)
    email.set_content(body_text, charset="utf-8")
    email.add_alternative(
        f"<pre style='white-space: pre-wrap; font-family: Consolas, monospace;'>{body_text}</pre>",
        subtype="html",
        charset="utf-8",
    )

    attachment_bytes = attachment_path.read_bytes()
    email.add_attachment(
        attachment_bytes,
        maintype="application",
        subtype="msword",
        filename=attachment_path.name,
    )
    return email


def _send_message(config: dict[str, str], email: EmailMessage) -> None:
    port = int(config["port"])
    if _is_enabled(config["use_ssl"]):
        with smtplib.SMTP_SSL(config["host"], port) as server:
            server.login(config["username"], config["password"])
            server.send_message(email)
    else:
        with smtplib.SMTP(config["host"], port) as server:
            server.starttls()
            server.login(config["username"], config["password"])
            server.send_message(email)


def send_report_email(report_path: Path, report_content: str) -> str:
    """Send the generated report to the configured mailbox."""
    config = _load_email_config()
    is_valid, message = _validate_config(config)
    if not is_valid:
        logger.warning(message)
        return message

    recipients = _parse_recipients(config["to_addr"])
    email = _build_email_message(
        from_addr=config["from_addr"],
        recipients=recipients,
        subject=f"基金分析报告 - {report_path.stem}",
        body_text=(
            "您好，\n\n"
            "以下为本次自动生成的基金分析报告正文，附件中同时包含 Word 文档版本。\n\n"
            f"{report_content}\n\n"
            "祝好。"
        ),
        attachment_path=report_path,
    )

    for attempt in range(1, MAX_EMAIL_RETRIES + 1):
        try:
            logger.info(
                "Starting email send attempt %s/%s to %s",
                attempt,
                MAX_EMAIL_RETRIES,
                ", ".join(recipients),
            )
            _send_message(config, email)
            logger.info("Email sent successfully.")
            return f"Email sent: {', '.join(recipients)}"
        except Exception:
            logger.exception("Email send failed on attempt %s.", attempt)
            if attempt < MAX_EMAIL_RETRIES:
                time.sleep(2)

    return "Email send failed. Please check logs/fund_analysis.log."


def send_report_email_to(
    report_path: Path,
    report_content: str,
    recipients: list[str],
    owner: str = "",
) -> str:
    """Send a report to explicit recipients while reusing SMTP settings."""
    config = _load_email_config()
    config["to_addr"] = ",".join(recipients)
    is_valid, message = _validate_config(config)
    if not is_valid:
        logger.warning(message)
        return message

    clean_recipients = _parse_recipients(config["to_addr"])
    display_owner = owner or "未命名用户"
    email = _build_email_message(
        from_addr=config["from_addr"],
        recipients=clean_recipients,
        subject=f"基金分析报告 - {display_owner} - {report_path.stem}",
        body_text=(
            f"您好，\n\n以下为 {display_owner} 的本次自动生成基金分析报告正文，"
            "附件中同时包含 Word 文档版本。\n\n"
            f"{report_content}\n\n"
            "祝好。"
        ),
        attachment_path=report_path,
    )

    for attempt in range(1, MAX_EMAIL_RETRIES + 1):
        try:
            logger.info(
                "Starting user email send attempt %s/%s for %s to %s",
                attempt,
                MAX_EMAIL_RETRIES,
                display_owner,
                ", ".join(clean_recipients),
            )
            _send_message(config, email)
            logger.info("User email sent successfully for %s.", display_owner)
            return f"Email sent for {display_owner}: {', '.join(clean_recipients)}"
        except Exception:
            logger.exception("User email send failed on attempt %s for %s.", attempt, display_owner)
            if attempt < MAX_EMAIL_RETRIES:
                time.sleep(2)

    return f"Email send failed for {display_owner}. Please check logs/fund_analysis.log."
