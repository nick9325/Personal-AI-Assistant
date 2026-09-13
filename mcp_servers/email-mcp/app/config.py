"""
Configuration for the Email MCP Server.

All settings are loaded from environment variables (optionally via a
.env file in the working directory). Nothing is hardcoded so the same
server image/process can be reused across environments.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class EmailSettings(BaseSettings):
    """Strongly-typed settings, validated once at process start."""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Required ---
    email_address: str = Field(..., description="Sender Gmail address")
    email_app_password: str = Field(
        ..., description="Gmail App Password (NOT your regular password)"
    )

    # --- SMTP connection ---
    smtp_host: str = Field(default="smtp.gmail.com")
    smtp_port: int = Field(default=587)
    smtp_use_tls: bool = Field(default=True)

    # --- Safety / operational limits ---
    max_recipients_per_call: int = Field(
        default=20, description="Hard cap on To/Cc/Bcc combined per send"
    )
    max_attachment_mb: float = Field(
        default=20.0, description="Hard cap per attachment, in megabytes"
    )
    default_display_name: str | None = Field(
        default=None, description="Optional 'From' display name, e.g. 'Nikhil B.'"
    )

    # --- Transport for running this MCP server itself ---
    mcp_transport: Literal["stdio", "sse", "streamable-http"] = Field(
        default="stdio", description="stdio | streamable-http"
    )
    mcp_host: str = Field(default="127.0.0.1", validation_alias="EMAIL_MCP_HOST")
    mcp_port: int = Field(default=8002, validation_alias="EMAIL_MCP_PORT")

    @field_validator("smtp_port", "mcp_port")
    @classmethod
    def _port_range(cls, v: int) -> int:
        if not (0 < v < 65536):
            raise ValueError("port must be between 1 and 65535")
        return v

    @field_validator("mcp_transport")
    @classmethod
    def _valid_transport(cls, v: str) -> str:
        allowed = {"stdio", "streamable-http"}
        if v not in allowed:
            raise ValueError(f"mcp_transport must be one of {allowed}")
        return v


@lru_cache(maxsize=1)
def get_settings() -> EmailSettings:
    """Cached settings instance — env is read once per process."""
    return EmailSettings()  # type: ignore[call-arg]
