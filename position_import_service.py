"""Recognize fund positions from screenshots."""

from __future__ import annotations

import base64
import json
import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


DEFAULT_PROVIDER = "zhipu"
DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"
DEFAULT_VISION_MODEL = "glm-4v-flash"

POSITION_IMPORT_PROMPT = """
你是一个基金持仓识别助手。请阅读这张基金持仓截图，只提取当前持仓列表里的基金信息。
请返回 JSON 数组，不要输出任何额外说明，不要使用 Markdown 代码块。每一项都必须是如下结构：
{
  "fund_code": "基金代码，没有就留空字符串",
  "fund_name": "基金名称",
  "holding_amount": 数字，必须是持仓金额、持有金额或市值，没有就填 0,
  "category": "根据名称可推断的分类，没有就留空字符串",
  "note": "OCR导入"
}

要求：
1. 只提取真实持仓，不要提取标题、按钮、收益率、总金额等无关内容。
2. 如果基金名称不完整，或者金额缺失、不完整、无法确认，就不要返回这一条。
3. 如果同一基金出现多次，只保留一条。
4. fund_name 不能为空，holding_amount 必须为大于 0 的数字。
5. 输出必须是合法 JSON 数组。
""".strip()


def _build_client() -> OpenAI:
    load_dotenv()
    provider = os.getenv("LLM_PROVIDER", DEFAULT_PROVIDER).strip().lower() or DEFAULT_PROVIDER
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    base_url = os.getenv("OPENAI_BASE_URL", "").strip()

    if not api_key:
        raise RuntimeError("未配置 OPENAI_API_KEY，无法识别截图")

    client_kwargs: dict[str, Any] = {"api_key": api_key}
    if provider == "zhipu":
        client_kwargs["base_url"] = base_url or DEFAULT_BASE_URL
    elif base_url:
        client_kwargs["base_url"] = base_url
    return OpenAI(**client_kwargs)


def _extract_json_array(text: str) -> list[dict]:
    content = (text or "").strip()
    if content.startswith("```"):
        content = content.strip("`")
        if "\n" in content:
            content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content[:-3].strip()

    start = content.find("[")
    end = content.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise ValueError("模型未返回合法的 JSON 数组")

    parsed = json.loads(content[start : end + 1])
    if not isinstance(parsed, list):
        raise ValueError("模型返回结果不是数组")
    return parsed


def _normalize_amount(value: Any) -> float | None:
    raw = str(value or "").strip().replace(",", "").replace("¥", "").replace("￥", "")
    if not raw:
        return None
    try:
        amount = float(raw)
    except (TypeError, ValueError):
        return None
    if amount <= 0:
        return None
    return round(amount, 2)


def _normalize_fund_code(value: Any) -> str:
    raw = str(value or "").strip()
    digits_only = "".join(char for char in raw if char.isdigit())
    if len(digits_only) == 6:
        return digits_only
    return ""


def _normalize_item(item: dict) -> dict | None:
    fund_name = str(item.get("fund_name", "")).strip()
    if not fund_name:
        return None

    holding_amount = _normalize_amount(item.get("holding_amount"))
    if holding_amount is None:
        return None

    fund_code = _normalize_fund_code(item.get("fund_code"))
    category = str(item.get("category", "")).strip()
    note = str(item.get("note", "")).strip() or "OCR导入"

    return {
        "fund_code": fund_code,
        "fund_name": fund_name,
        "holding_amount": holding_amount,
        "category": category,
        "note": note,
    }


def recognize_positions_from_image(image_bytes: bytes, mime_type: str) -> list[dict]:
    """Use the configured multimodal model to extract position rows from one screenshot."""
    client = _build_client()
    model = os.getenv("OPENAI_VISION_MODEL", "").strip() or DEFAULT_VISION_MODEL
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{base64_image}"

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": POSITION_IMPORT_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
    )
    content = (response.choices[0].message.content or "").strip()
    parsed = _extract_json_array(content)

    unique_items: list[dict] = []
    seen_keys: set[str] = set()
    for item in parsed:
        if not isinstance(item, dict):
            continue
        normalized = _normalize_item(item)
        if normalized is None:
            continue
        dedupe_key = normalized["fund_code"] or normalized["fund_name"]
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        unique_items.append(normalized)

    if not unique_items:
        raise ValueError("未识别到名称和金额都完整的基金持仓")

    return unique_items
