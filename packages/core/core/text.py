"""Turn outside HTML into plain text. Content from posts and emails is data, never markup."""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser

_BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "blockquote"}
_SKIP = {"script", "style", "head", "title", "noscript", "template", "svg"}


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP:
            self.skip += 1
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP and self.skip:
            self.skip -= 1
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.parts.append(data)


def html_to_text(value: str | None, limit: int = 50_000) -> str:
    if not value:
        return ""
    parser = _Text()
    try:
        parser.feed(value)
        parser.close()
        text = "".join(parser.parts)
    except Exception:
        text = re.sub(r"<[^>]*>", " ", value)
    text = html.unescape(text).replace("\x00", "")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()[:limit]
