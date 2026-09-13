from __future__ import annotations

import os
import re
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_TASKS_SCHEMA = """
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT DEFAULT '',
        status TEXT NOT NULL DEFAULT 'pending',
        priority INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
"""


class DatabaseValidationError(ValueError):
    pass


class DatabaseService:
    def __init__(self, database_path: str | Path | None = None) -> None:
        configured_path = Path(database_path or os.getenv("DATABASE_PATH", "data/assistant.db"))
        workspace_root = Path(__file__).resolve().parents[3]
        self.database_path = (
            configured_path if configured_path.is_absolute() else workspace_root / configured_path
        )
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute(_TASKS_SCHEMA)

    @staticmethod
    def _identifier(value: str) -> str:
        if value == "*" or not _IDENTIFIER.fullmatch(value):
            raise DatabaseValidationError(f"Invalid SQL identifier: {value}")
        return value

    def _table_columns(self, table: str) -> set[str]:
        table = self._identifier(table)
        with self._connection() as connection:
            rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
        if not rows:
            raise DatabaseValidationError(f"Unknown table: {table}")
        return {row[1] for row in rows}

    def _validate_columns(self, table: str, columns: list[str]) -> None:
        available = self._table_columns(table)
        invalid = set(columns) - available
        if invalid:
            raise DatabaseValidationError(f"Unknown column(s) for {table}: {sorted(invalid)}")

    def schema(self, table: str | None = None) -> list[dict[str, Any]]:
        with self._connection() as connection:
            if table:
                self._table_columns(table)
                tables = [table]
            else:
                tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
            result = []
            for name in tables:
                rows = connection.execute(f"PRAGMA table_info({self._identifier(name)})").fetchall()
                result.append({"table": name, "columns": [dict(row) for row in rows]})
            return result

    def get_records(self, table: str, columns: list[str], filters: dict[str, str], limit: int) -> list[dict[str, Any]]:
        table = self._identifier(table)
        selected = ["*"] if columns == ["*"] else [self._identifier(column) for column in columns]
        if selected == []:
            raise DatabaseValidationError("At least one column is required")
        if selected != ["*"]:
            self._validate_columns(table, selected)
        self._validate_columns(table, list(filters))
        where = " AND ".join(f"{self._identifier(key)} = ?" for key in filters)
        query = f"SELECT {', '.join(selected)} FROM {table}"
        if where:
            query += f" WHERE {where}"
        query += " LIMIT ?"
        with self._connection() as connection:
            return [dict(row) for row in connection.execute(query, [*filters.values(), limit]).fetchall()]

    def create_record(self, table: str, values: dict[str, Any]) -> int:
        table = self._identifier(table)
        self._validate_columns(table, list(values))
        columns = [self._identifier(key) for key in values]
        placeholders = ", ".join("?" for _ in columns)
        with self._connection() as connection:
            cursor = connection.execute(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})", list(values.values()))
            if cursor.lastrowid is None:
                raise DatabaseValidationError("SQLite did not return a record id")
            return int(cursor.lastrowid)

    def update_records(self, table: str, values: dict[str, Any], filters: dict[str, str]) -> int:
        table = self._identifier(table)
        self._validate_columns(table, [*values, *filters])
        assignments = ", ".join(f"{self._identifier(key)} = ?" for key in values)
        where = " AND ".join(f"{self._identifier(key)} = ?" for key in filters)
        with self._connection() as connection:
            cursor = connection.execute(f"UPDATE {table} SET {assignments} WHERE {where}", [*values.values(), *filters.values()])
            return cursor.rowcount

    def delete_records(self, table: str, filters: dict[str, str]) -> int:
        table = self._identifier(table)
        self._validate_columns(table, list(filters))
        where = " AND ".join(f"{self._identifier(key)} = ?" for key in filters)
        with self._connection() as connection:
            cursor = connection.execute(f"DELETE FROM {table} WHERE {where}", list(filters.values()))
            return cursor.rowcount
