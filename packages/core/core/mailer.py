"""Outgoing email behind a small interface, so the provider can be swapped.

Locally this is SMTP to Mailpit (http://127.0.0.1:54324). A transactional provider
replaces `SmtpMailer` later without changing callers.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

from core.settings import get_settings

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    text: str


class Mailer(Protocol):
    async def send(self, email: Email) -> bool: ...


class SmtpMailer:
    def __init__(self, host: str, port: int, sender: str, timeout: float = 10.0) -> None:
        self.host, self.port, self.sender, self.timeout = host, port, sender, timeout

    def _send_sync(self, email: Email) -> None:
        msg = EmailMessage()
        msg["From"] = self.sender
        msg["To"] = email.to
        msg["Subject"] = email.subject
        msg.set_content(email.text)
        with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as smtp:
            smtp.send_message(msg)

    async def send(self, email: Email) -> bool:
        """Returns False instead of raising: a failed email must not fail the request."""
        try:
            await asyncio.to_thread(self._send_sync, email)
            return True
        except (OSError, ValueError, smtplib.SMTPException):
            log.warning("email_send_failed", extra={"subject": email.subject}, exc_info=True)
            return False


def get_mailer() -> Mailer:
    s = get_settings()
    return SmtpMailer(s.smtp_host, s.smtp_port, s.smtp_from)
