from __future__ import annotations

from pydantic import BaseModel, Field


class FileSearchRequest(BaseModel):
    directory: str = "."
    pattern: str = "*"
    recursive: bool = True
    max_results: int = Field(default=100, ge=1, le=1000)


class FilePathRequest(BaseModel):
    path: str = Field(min_length=1)


class CreateDirectoryRequest(BaseModel):
    path: str = Field(min_length=1)


class MoveRequest(BaseModel):
    source: str = Field(min_length=1)
    destination: str = Field(min_length=1)


class DeleteRequest(BaseModel):
    path: str = Field(min_length=1)
    recursive: bool = False
