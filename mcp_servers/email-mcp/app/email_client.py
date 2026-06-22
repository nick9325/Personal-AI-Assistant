"""
Core SMTP email-sending logic.

Deliberately framework-agnostic: nothing here imports `mcp`. The MCP
tool layer (server.py) wraps these functions and is responsible for
turning exceptions into the error-string return values that MCP tools
should use instead of raising.
"""

from __future__ import annotations

import mimetypes
import os
import re
import smtplib
import ssl
from dataclasses import dataclass, field
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path

from .config import EmailSettings

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class EmailValidationError(ValueError):
    """Raised for bad input before any network call is attempted."""


@dataclass
class SendResult:
    ok: bool
    message: str
    recipients: list[str] = field(default_factory=list)


def _split_recipients(value: str | list[str] | None) -> list[str]:
    """Accept either a comma-separated string or a list, return a clean list."""
    if value is None:
        return []
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",")]
    else:
        parts = [p.strip() for p in value]
    return [p for p in parts if p]


def _validate_addresses(addresses: list[str], field_name: str) -> None:
    for addr in addresses:
        if not _EMAIL_RE.match(addr):
            raise EmailValidationError(f"Invalid email address in {field_name}: '{addr}'")


def _build_message(
    *,
    settings: EmailSettings,
    to: list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    html: bool = False,
    attachment_paths: list[str] | None = None,
) -> tuple[MIMEMultipart, list[str]]:
    """Build the MIME message. Returns (message, full_recipient_list)."""

    cc = cc or []
    bcc = bcc or []
    attachment_paths = attachment_paths or []

    all_recipients = to + cc + bcc
    if not all_recipients:
        raise EmailValidationError("At least one recipient (to/cc/bcc) is required")

    if len(all_recipients) > settings.max_recipients_per_call:
        raise EmailValidationError(
            f"Too many recipients ({len(all_recipients)}); "
            f"limit is {settings.max_recipients_per_call} per call"
        )

    _validate_addresses(to, "to")
    _validate_addresses(cc, "cc")
    _validate_addresses(bcc, "bcc")

    if not subject or not subject.strip():
        raise EmailValidationError("Subject must not be empty")
    if not body or not body.strip():
        raise EmailValidationError("Body must not be empty")

    message = MIMEMultipart("mixed")

    from_header = settings.email_address
    if settings.default_display_name:
        from_header = formataddr((settings.default_display_name, settings.email_address))

    message["From"] = from_header
    message["To"] = ", ".join(to)
    if cc:
        message["Cc"] = ", ".join(cc)
    message["Subject"] = subject

    body_part = MIMEMultipart("alternative")
    body_part.attach(MIMEText(body, "html" if html else "plain", "utf-8"))
    message.attach(body_part)

    for raw_path in attachment_paths:
        _attach_file(message, raw_path, settings.max_attachment_mb)

    return message, all_recipients


def _attach_file(message: MIMEMultipart, raw_path: str, max_mb: float) -> None:
    path = Path(raw_path).expanduser()

    if not path.exists() or not path.is_file():
        raise EmailValidationError(f"Attachment not found: {raw_path}")

    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > max_mb:
        raise EmailValidationError(
            f"Attachment '{path.name}' is {size_mb:.1f} MB, "
            f"exceeding the {max_mb} MB limit"
        )

    content_type, _ = mimetypes.guess_type(str(path))
    content_type = content_type or "application/octet-stream"
    maintype, _, subtype = content_type.partition("/")

    with path.open("rb") as f:
        data = f.read()

    if maintype == "text":
        part = MIMEText(data.decode("utf-8", errors="replace"), subtype or "plain")
    else:
        part = MIMEApplication(data, _subtype=subtype or "octet-stream")

    part.add_header("Content-Disposition", "attachment", filename=path.name)
    message.attach(part)


def send_smtp_email(
    settings: EmailSettings,
    *,
    to: str | list[str],
    subject: str,
    body: str,
    cc: str | list[str] | None = None,
    bcc: str | list[str] | None = None,
    html: bool = False,
    attachment_paths: list[str] | None = None,
) -> SendResult:
    """
    Synchronous SMTP send. Raises EmailValidationError for bad input
    (caught by the caller before any connection is opened) and lets
    smtplib/ssl exceptions propagate for the caller to translate.
    """

    to_list = _split_recipients(to)
    cc_list = _split_recipients(cc)
    bcc_list = _split_recipients(bcc)

    message, all_recipients = _build_message(
        settings=settings,
        to=to_list,
        subject=subject,
        body=body,
        cc=cc_list,
        bcc=bcc_list,
        html=html,
        attachment_paths=attachment_paths,
    )

    context = ssl.create_default_context()

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
        if settings.smtp_use_tls:
            server.starttls(context=context)
        server.login(settings.email_address, settings.email_app_password)
        server.sendmail(settings.email_address, all_recipients, message.as_string())

    return SendResult(
        ok=True,
        message=f"Email sent to {len(all_recipients)} recipient(s)",
        recipients=all_recipients,
    )
