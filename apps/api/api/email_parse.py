"""Turn an inbound email into a raw item. Text from emails is data, never instructions.

* Upwork job alert emails (forwarded by the user): title, budget, job link.
* Anything else: subject as title, plain text as body, first web link.
Attachments are never read. HTML is reduced to text. The sender's address is not stored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from core.text import html_to_text

LINK = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)
UPWORK_JOB = re.compile(
    r"https?://(?:www\.)?upwork\.com/(?:jobs|freelance-jobs/apply|ab/proposals/job)/[^\s<>\"')\]]+",
    re.IGNORECASE,
)
BUDGET = re.compile(
    r"(?:Budget|Fixed[- ]price|Est\.? budget)\s*:?\s*\$?\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE
)
HOURLY = re.compile(
    r"Hourly(?: Range)?\s*:?\s*\$?\s*([\d.]+)\s*(?:-|to)\s*\$?\s*([\d.]+)", re.IGNORECASE
)
SUBJECT_PREFIX = re.compile(
    r"^\s*(?:(?:fwd?|fw|re)\s*:\s*)*(?:new job\s*:|job alert\s*:)?\s*", re.IGNORECASE
)


@dataclass
class ParsedEmail:
    title: str
    body: str
    url: str | None
    external_id: str | None
    payload: dict[str, Any] = field(default_factory=dict)


def _text(plain: str | None, html: str | None) -> str:
    return (plain or "").strip() or html_to_text(html)


def is_upwork(sender: str, subject: str, text: str) -> bool:
    return (
        "upwork" in (sender or "").lower()
        or bool(UPWORK_JOB.search(text))
        or ("upwork" in subject.lower() and "job" in subject.lower())
    )


def parse_upwork(subject: str, text: str) -> ParsedEmail:
    link = UPWORK_JOB.search(text)
    url = link.group(0).rstrip(".,") if link else None
    job_id = re.search(r"~0?[0-9a-z]{6,}", url or "")
    payload: dict[str, Any] = {"parser": "upwork"}
    if m := BUDGET.search(text):
        payload["budget_usd"] = float(m.group(1).replace(",", ""))
    if m := HOURLY.search(text):
        payload["hourly_usd"] = [float(m.group(1)), float(m.group(2))]
    title = SUBJECT_PREFIX.sub("", subject).strip()
    title = re.sub(r"\s*-\s*Upwork\s*$", "", title, flags=re.IGNORECASE) or "Upwork job"
    return ParsedEmail(
        title=title[:500],
        body=text[:20000],
        url=url,
        external_id=f"upwork:{job_id.group(0)}" if job_id else None,
        payload=payload,
    )


def parse_general(subject: str, text: str) -> ParsedEmail:
    link = LINK.search(text)
    return ParsedEmail(
        title=(SUBJECT_PREFIX.sub("", subject).strip() or "Email")[:500],
        body=text[:20000],
        url=link.group(0).rstrip(".,") if link else None,
        external_id=None,
        payload={"parser": "general"},
    )


def parse_email(sender: str, subject: str, plain: str | None, html: str | None) -> ParsedEmail:
    text = _text(plain, html)
    return (
        parse_upwork(subject, text)
        if is_upwork(sender, subject, text)
        else parse_general(subject, text)
    )
