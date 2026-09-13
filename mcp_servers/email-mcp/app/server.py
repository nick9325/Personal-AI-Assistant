"""
Email MCP Server
=================

Exposes Gmail-SMTP email sending as MCP tools so any MCP-compatible
agent (LangGraph, Claude Desktop, Claude Code, etc.) can send email
without that logic living inline in the agent's own tool file.

Run standalone:
    python -m src.server                # uses MCP_TRANSPORT from .env (default stdio)

Run as HTTP (to mirror your Personal Memory MCP server on its own port):
    MCP_TRANSPORT=streamable-http MCP_PORT=8001 python -m src.server

Required environment variables (see .env.example):
    EMAIL_ADDRESS
    EMAIL_APP_PASSWORD

Design notes
------------
- All tool functions catch exceptions and return error strings rather
  than raising. Raising inside an MCP tool surfaces as a generic
  "tool execution failed" to the calling LLM with no useful detail;
  returning a descriptive string lets the agent see exactly what
  went wrong (bad recipient, missing attachment, auth failure, etc.)
  and decide whether to retry or report back to the user.
- Credentials are validated at startup (lifespan), not on first tool
  call, so misconfiguration fails fast and loudly in the server logs
  rather than surfacing as a confusing error on a user's first send.
"""

from __future__ import annotations

import logging
import smtplib
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server.fastmcp import Context, FastMCP

from .config import EmailSettings, get_settings
from .email_client import EmailValidationError, send_smtp_email

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("email-mcp")


@dataclass
class AppContext:
    settings: EmailSettings


def _verify_credentials(settings: EmailSettings) -> None:
    """Fail fast at startup if SMTP login doesn't work."""
    context_msg = (
        f"host={settings.smtp_host} port={settings.smtp_port} "
        f"user={settings.email_address}"
    )
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            if settings.smtp_use_tls:
                server.starttls()
            server.login(settings.email_address, settings.email_app_password)
        logger.info("SMTP credential check passed (%s)", context_msg)
    except smtplib.SMTPAuthenticationError as exc:
        logger.error(
            "SMTP auth failed at startup (%s): %s. "
            "Check EMAIL_APP_PASSWORD is a Gmail App Password, not your login password.",
            context_msg,
            exc,
        )
        raise
    except Exception as exc:  # noqa: BLE001 - we want startup to fail loudly either way
        logger.error("SMTP connectivity check failed at startup (%s): %s", context_msg, exc)
        raise


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncGenerator[AppContext, None]:
    settings = get_settings()
    _verify_credentials(settings)
    try:
        yield AppContext(settings=settings)
    finally:
        logger.info("Email MCP server shutting down")


_settings_for_init = get_settings()

mcp = FastMCP(
    "email-mcp",
    host=_settings_for_init.mcp_host,
    port=_settings_for_init.mcp_port,
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def send_email(
    ctx: Context,
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
    bcc: str | None = None,
) -> str:
    """
    Send a plain-text email via Gmail SMTP.

    Args:
        to: Recipient address, or comma-separated list of addresses.
        subject: Email subject line.
        body: Plain-text email body.
        cc: Optional comma-separated CC addresses.
        bcc: Optional comma-separated BCC addresses.

    Returns:
        A human-readable success or error string.
    """
    app: AppContext = ctx.request_context.lifespan_context
    try:
        result = send_smtp_email(
            app.settings,
            to=to,
            subject=subject,
            body=body,
            cc=cc,
            bcc=bcc,
            html=False,
        )
        return result.message
    except EmailValidationError as exc:
        return f"Could not send email: {exc}"
    except smtplib.SMTPAuthenticationError:
        return (
            "Could not send email: SMTP authentication failed. "
            "Verify EMAIL_ADDRESS and EMAIL_APP_PASSWORD are correct "
            "and that the app password hasn't been revoked."
        )
    except smtplib.SMTPRecipientsRefused as exc:
        return f"Could not send email: one or more recipients were refused: {exc.recipients}"
    except (smtplib.SMTPException, OSError) as exc:
        return f"Could not send email due to an SMTP/network error: {exc}"
    except Exception as exc:  # noqa: BLE001 - last-resort guard so the tool never raises
        logger.exception("Unexpected error in send_email")
        return f"Could not send email due to an unexpected error: {exc}"


@mcp.tool()
async def send_email_html(
    ctx: Context,
    to: str,
    subject: str,
    html_body: str,
    cc: str | None = None,
    bcc: str | None = None,
) -> str:
    """
    Send an HTML-formatted email via Gmail SMTP. Use this for emails
    that benefit from formatting (lists, bold text, links, simple
    layout) such as generated reports or summaries.

    Args:
        to: Recipient address, or comma-separated list of addresses.
        subject: Email subject line.
        html_body: HTML content of the email body.
        cc: Optional comma-separated CC addresses.
        bcc: Optional comma-separated BCC addresses.

    Returns:
        A human-readable success or error string.
    """
    app: AppContext = ctx.request_context.lifespan_context
    try:
        result = send_smtp_email(
            app.settings,
            to=to,
            subject=subject,
            body=html_body,
            cc=cc,
            bcc=bcc,
            html=True,
        )
        return result.message
    except EmailValidationError as exc:
        return f"Could not send email: {exc}"
    except smtplib.SMTPAuthenticationError:
        return "Could not send email: SMTP authentication failed. Check credentials."
    except smtplib.SMTPRecipientsRefused as exc:
        return f"Could not send email: recipients refused: {exc.recipients}"
    except (smtplib.SMTPException, OSError) as exc:
        return f"Could not send email due to an SMTP/network error: {exc}"
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error in send_email_html")
        return f"Could not send email due to an unexpected error: {exc}"


@mcp.tool()
async def send_email_with_attachments(
    ctx: Context,
    to: str,
    subject: str,
    body: str,
    attachment_paths: list[str],
    cc: str | None = None,
    bcc: str | None = None,
    html: bool = False,
) -> str:
    """
    Send an email with one or more file attachments via Gmail SMTP.

    Args:
        to: Recipient address, or comma-separated list of addresses.
        subject: Email subject line.
        body: Email body (plain text unless html=True).
        attachment_paths: Absolute or user-relative file paths to attach.
        cc: Optional comma-separated CC addresses.
        bcc: Optional comma-separated BCC addresses.
        html: Whether `body` is HTML.

    Returns:
        A human-readable success or error string.
    """
    app: AppContext = ctx.request_context.lifespan_context
    try:
        result = send_smtp_email(
            app.settings,
            to=to,
            subject=subject,
            body=body,
            cc=cc,
            bcc=bcc,
            html=html,
            attachment_paths=attachment_paths,
        )
        return result.message
    except EmailValidationError as exc:
        return f"Could not send email: {exc}"
    except smtplib.SMTPAuthenticationError:
        return "Could not send email: SMTP authentication failed. Check credentials."
    except smtplib.SMTPRecipientsRefused as exc:
        return f"Could not send email: recipients refused: {exc.recipients}"
    except (smtplib.SMTPException, OSError) as exc:
        return f"Could not send email due to an SMTP/network error: {exc}"
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error in send_email_with_attachments")
        return f"Could not send email due to an unexpected error: {exc}"


# ---------------------------------------------------------------------------
# Resource — lets an agent (or you) introspect server config without
# leaking the actual secret values.
# ---------------------------------------------------------------------------


@mcp.resource("email://config")
def get_config_summary() -> str:
    """Non-secret summary of the current email server configuration."""
    settings = get_settings()
    return (
        f"sender={settings.email_address}\n"
        f"smtp_host={settings.smtp_host}\n"
        f"smtp_port={settings.smtp_port}\n"
        f"tls={settings.smtp_use_tls}\n"
        f"max_recipients_per_call={settings.max_recipients_per_call}\n"
        f"max_attachment_mb={settings.max_attachment_mb}"
    )


def main() -> None:
    settings = get_settings()
    logger.info(
        "Starting email MCP server with %s transport on %s:%s",
        settings.mcp_transport,
        settings.mcp_host,
        settings.mcp_port,
    )
    mcp.run(transport=settings.mcp_transport)


if __name__ == "__main__":
    main()
