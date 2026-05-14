"""Fetch fund-related market news from public finance sources."""

from __future__ import annotations

from typing import Iterable
from urllib.parse import urljoin

import feedparser
import requests
from bs4 import BeautifulSoup


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/135.0.0.0 Safari/537.36"
)

RSS_LIST = [
    "https://feeds.feedburner.com/ftchinese/feed",
]

DEFAULT_LIMIT_PER_FEED = 5
REQUEST_TIMEOUT = 12
HTML_SOURCES = [
    {
        "name": "新浪财经 7x24",
        "url": "https://finance.sina.com.cn/7x24/",
        "parser": "sina_7x24",
    },
]


def _clean_text(value: str | None) -> str:
    return " ".join((value or "").split())


def _entry_to_line(entry) -> str:
    title = _clean_text(getattr(entry, "title", "无标题"))
    summary = _clean_text(getattr(entry, "summary", ""))
    link = _clean_text(getattr(entry, "link", ""))

    parts = [f"- {title}"]
    if summary:
        parts.append(f"  摘要：{summary[:120]}")
    if link:
        parts.append(f"  链接：{link}")
    return "\n".join(parts)


def _line_from_text(title: str, link: str = "", summary: str = "") -> str:
    parts = [f"- {_clean_text(title)}"]
    if summary:
        parts.append(f"  摘要：{_clean_text(summary)[:120]}")
    if link:
        parts.append(f"  链接：{_clean_text(link)}")
    return "\n".join(parts)


def _fetch_rss_items(
    rss_list: Iterable[str],
    limit_per_feed: int,
    errors: list[str],
) -> list[str]:
    items: list[str] = []

    for url in rss_list:
        feed = feedparser.parse(url, agent=USER_AGENT)
        if getattr(feed, "bozo", False) and not getattr(feed, "entries", None):
            error = getattr(feed, "bozo_exception", "未知 RSS 错误")
            errors.append(f"RSS 失败：{url} -> {error}")
            continue

        for entry in feed.entries[:limit_per_feed]:
            items.append(_entry_to_line(entry))

    return items


def _fetch_html(url: str) -> str:
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def _parse_sina_7x24(html: str, base_url: str, limit: int) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[str] = []
    seen: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "").strip()
        title = _clean_text(anchor.get_text(" ", strip=True))

        if not title or len(title) < 12:
            continue
        if title in seen:
            continue
        if "新浪" in title or "财经首页" in title or "更多" == title:
            continue
        if "7x24" not in href and "cj.sina.cn" not in href and "finance.sina.com.cn" not in href:
            continue

        seen.add(title)
        items.append(_line_from_text(title=title, link=urljoin(base_url, href)))
        if len(items) >= limit:
            break

    return items


def _fetch_html_items(limit_per_feed: int, errors: list[str]) -> list[str]:
    items: list[str] = []

    for source in HTML_SOURCES:
        try:
            html = _fetch_html(source["url"])
            if source["parser"] == "sina_7x24":
                parsed = _parse_sina_7x24(html, source["url"], limit_per_feed)
            else:
                parsed = []

            if not parsed:
                errors.append(f"网页抓取为空：{source['name']} -> {source['url']}")
                continue

            items.extend(parsed)
        except Exception as exc:
            errors.append(f"网页抓取失败：{source['name']} -> {exc}")

    return items


def fetch_news(
    rss_list: Iterable[str] | None = None,
    limit_per_feed: int = DEFAULT_LIMIT_PER_FEED,
) -> list[str]:
    """Fetch and format recent news from configured sources."""
    errors: list[str] = []
    items = _fetch_html_items(limit_per_feed=limit_per_feed, errors=errors)

    if not items:
        items = _fetch_rss_items(
            rss_list=list(rss_list or RSS_LIST),
            limit_per_feed=limit_per_feed,
            errors=errors,
        )

    if not items and errors:
        return [f"- {error}" for error in errors]

    return items


if __name__ == "__main__":
    news_items = fetch_news()
    if not news_items:
        print("未抓取到新闻，请检查网络或 RSS 地址。")
    else:
        print("已抓取到以下新闻：\n")
        print("\n\n".join(news_items))
