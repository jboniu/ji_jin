"""Export generated report text to a Word-compatible .doc file."""

from __future__ import annotations

from html import escape
from pathlib import Path


def _markdown_like_to_html(report_title: str, report_content: str) -> str:
    """Convert simple markdown-like text into HTML that Word can open."""
    html_parts: list[str] = [
        "<html>",
        "<head>",
        '<meta charset="utf-8">',
        "<style>",
        "body { font-family: 'Microsoft YaHei', Arial, sans-serif; line-height: 1.7; margin: 28px; }",
        "h1 { font-size: 24px; margin-bottom: 16px; }",
        "h2 { font-size: 18px; margin-top: 20px; margin-bottom: 10px; color: #1f1f1f; }",
        "h3 { font-size: 16px; margin-top: 16px; margin-bottom: 8px; }",
        "p { margin: 8px 0; }",
        "ul { margin: 6px 0 10px 24px; }",
        "li { margin: 4px 0; }",
        ".divider { margin: 18px 0; border-top: 1px solid #d9d9d9; }",
        "</style>",
        "</head>",
        "<body>",
        f"<h1>{escape(report_title)}</h1>",
    ]

    in_list = False
    for raw_line in report_content.splitlines():
        line = raw_line.strip()

        if not line:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            continue

        if line == "---":
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append('<div class="divider"></div>')
            continue

        if line.startswith("## "):
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append(f"<h2>{escape(line[3:].strip())}</h2>")
            continue

        if line.startswith("# "):
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append(f"<h1>{escape(line[2:].strip())}</h1>")
            continue

        if line.startswith("### "):
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append(f"<h3>{escape(line[4:].strip())}</h3>")
            continue

        if line.startswith("- "):
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            html_parts.append(f"<li>{escape(line[2:].strip())}</li>")
            continue

        if in_list:
            html_parts.append("</ul>")
            in_list = False
        html_parts.append(f"<p>{escape(line)}</p>")

    if in_list:
        html_parts.append("</ul>")

    html_parts.extend(["</body>", "</html>"])
    return "\n".join(html_parts)


def export_report_to_doc(report_title: str, report_content: str, output_path: Path) -> Path:
    """Export markdown-like report text into a Word-compatible .doc file."""
    html_content = _markdown_like_to_html(report_title, report_content)
    output_path.write_text(html_content, encoding="utf-8")
    return output_path
