from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TableRequest(BaseModel):
    table: str = Field(min_length=1, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")


class GetRecordsRequest(TableRequest):
    columns: list[str] = Field(default_factory=lambda: ["*"])
    filters: dict[str, str] = Field(default_factory=dict)
    limit: int = Field(default=100, ge=1, le=500)


class CreateRecordRequest(TableRequest):
    values: dict[str, Any] = Field(min_length=1)


class UpdateRecordRequest(TableRequest):
    values: dict[str, Any] = Field(min_length=1)
    filters: dict[str, str] = Field(min_length=1)


class DeleteRecordRequest(TableRequest):
    filters: dict[str, str] = Field(min_length=1)
