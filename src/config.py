from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

from dotenv import load_dotenv

if TYPE_CHECKING:
    from langchain_mcp_adapters.sessions import Connection

ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT_DIR / ".env"

load_dotenv(ENV_FILE)


@dataclass(frozen=True)
class MCPServerConfig:
    name: str
    url: str
    enabled: bool = True

    @property
    def connection(self) -> "Connection":
        return cast("Connection", {"transport": "streamable_http", "url": self.url})


def _is_enabled(value: str | None) -> bool:
    return (value or "true").strip().lower() in {"1", "true", "yes", "on"}


def get_mcp_servers() -> tuple[MCPServerConfig, ...]:
    defaults = (
        ("weather", "http://127.0.0.1:8000/mcp"),
        ("email", "http://127.0.0.1:8001/mcp"),
        ("personal_memory", "http://127.0.0.1:8003/mcp"),
        ("filesystem", "http://127.0.0.1:8004/mcp"),
        ("database", "http://127.0.0.1:8005/mcp"),
    )
    return tuple(
        MCPServerConfig(
            name=name,
            url=os.getenv(f"{name.upper()}_MCP_URL", default_url),
            enabled=_is_enabled(os.getenv(f"{name.upper()}_MCP_ENABLED")),
        )
        for name, default_url in defaults
    )


def get_llm_settings() -> tuple[str | None, str]:
    return (
        os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"),
        os.getenv("LLM_MODEL", "gemini-2.5-flash"),
    )


def get_checkpoint_path() -> Path:
    configured_path = Path(os.getenv("CHECKPOINT_DATABASE_PATH", "data/checkpoints.sqlite"))
    return configured_path if configured_path.is_absolute() else ROOT_DIR / configured_path
