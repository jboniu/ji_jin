"""Load and format user fund portfolio profiles."""

from __future__ import annotations

import json
from pathlib import Path


PORTFOLIO_PATH = Path("portfolio.json")
USERS_PATH = Path("users.json")


def load_portfolio(path: Path = PORTFOLIO_PATH) -> dict:
    """Load portfolio data from JSON."""
    if not path.exists():
        return {
            "owner": "未配置",
            "currency": "CNY",
            "positions": [],
        }

    return json.loads(path.read_text(encoding="utf-8"))


def load_users(path: Path = USERS_PATH) -> list[dict]:
    """Load multi-user portfolio data from JSON."""
    if not path.exists():
        return []

    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("users", [])


def build_portfolio_summary(portfolio: dict) -> str:
    """Convert portfolio data into readable text for reports and prompts."""
    owner = portfolio.get("owner", "未配置")
    currency = portfolio.get("currency", "CNY")
    positions = portfolio.get("positions", [])

    if not positions:
        return f"持仓用户：{owner}\n计价货币：{currency}\n当前未配置持仓。"

    lines = [
        f"持仓用户：{owner}",
        f"计价货币：{currency}",
        "当前持仓结构：",
    ]
    total = 0.0

    for item in positions:
        fund_code = str(item.get("fund_code", "")).strip()
        fund_name = str(item.get("fund_name", "")).strip()
        category = str(item.get("category", "未命名类别")).strip()
        allocation = float(item.get("allocation_percent", 0) or 0)
        note = str(item.get("note", "")).strip()
        total += allocation

        identity = category
        if fund_code and fund_name:
            identity = f"{fund_code} {fund_name} | {category}"
        elif fund_name:
            identity = f"{fund_name} | {category}"
        elif fund_code:
            identity = f"{fund_code} | {category}"

        line = f"- {identity}：{allocation}%"
        if note:
            line += f"（{note}）"
        lines.append(line)

    lines.append(f"总仓位占比合计：{total:.4f}%")
    return "\n".join(lines)


def build_user_summary(user: dict) -> str:
    """Build a readable summary for one configured user."""
    owner = user.get("owner", "未命名用户")
    user_id = user.get("user_id", "unknown")
    emails = user.get("email_to", [])
    subscribed = bool(user.get("subscribe_email_reports", False))
    email_text = ", ".join(emails) if emails else "未配置邮箱"

    portfolio_text = build_portfolio_summary(user)
    return (
        f"用户ID：{user_id}\n"
        f"用户名称：{owner}\n"
        f"报告邮件订阅：{'已开启' if subscribed else '已关闭'}\n"
        f"接收邮箱：{email_text}\n"
        f"{portfolio_text}"
    )


def normalize_single_user_portfolio(portfolio: dict) -> dict:
    """Convert legacy single-user portfolio data into the shared user shape."""
    return {
        "user_id": "default_user",
        "owner": portfolio.get("owner", "默认用户"),
        "email_to": [],
        "subscribe_email_reports": False,
        "currency": portfolio.get("currency", "CNY"),
        "positions": portfolio.get("positions", []),
    }


if __name__ == "__main__":
    users = load_users()
    if users:
        for index, user in enumerate(users, start=1):
            print(f"===== USER {index} =====")
            print(build_user_summary(user))
            print()
    else:
        portfolio = load_portfolio()
        print(build_portfolio_summary(portfolio))
