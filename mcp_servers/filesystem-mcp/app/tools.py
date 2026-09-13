from __future__ import annotations

import fnmatch
import os
import shutil
from dataclasses import dataclass
from pathlib import Path


class FilesystemPolicyError(ValueError):
    pass


@dataclass(frozen=True)
class FilesystemPolicy:
    allowed_roots: tuple[Path, ...]
    blocked_names: frozenset[str] = frozenset({".ssh", ".aws", ".azure", ".gnupg"})
    max_read_bytes: int = 2_000_000

    @classmethod
    def from_environment(cls) -> "FilesystemPolicy":
        raw_roots = os.getenv("FILESYSTEM_ALLOWED_ROOTS", "").strip()
        if raw_roots:
            roots = tuple(Path(value).expanduser().resolve() for value in raw_roots.split(os.pathsep) if value)
        else:
            roots = (Path.cwd().resolve(),)
        return cls(allowed_roots=roots)

    def resolve(self, raw_path: str) -> Path:
        candidate = Path(raw_path).expanduser()
        if not candidate.is_absolute():
            candidate = self.allowed_roots[0] / candidate
        resolved = candidate.resolve()
        if not any(resolved == root or root in resolved.parents for root in self.allowed_roots):
            raise FilesystemPolicyError(f"Path is outside allowed workspace roots: {raw_path}")
        if any(part.lower() in self.blocked_names for part in resolved.parts):
            raise FilesystemPolicyError(f"Access to protected path is blocked: {raw_path}")
        return resolved


class FilesystemService:
    def __init__(self, policy: FilesystemPolicy | None = None) -> None:
        self.policy = policy or FilesystemPolicy.from_environment()

    def search(self, directory: str, pattern: str, recursive: bool, max_results: int) -> list[str]:
        root = self.policy.resolve(directory)
        if not root.is_dir():
            raise FilesystemPolicyError(f"Directory does not exist: {directory}")
        iterator = root.rglob("*") if recursive else root.glob("*")
        matches: list[str] = []
        for path in iterator:
            if path.is_file() and fnmatch.fnmatch(path.name, pattern):
                matches.append(str(path))
                if len(matches) >= max_results:
                    break
        return matches

    def read(self, path: str) -> str:
        target = self.policy.resolve(path)
        if not target.is_file():
            raise FilesystemPolicyError(f"File does not exist: {path}")
        if target.stat().st_size > self.policy.max_read_bytes:
            raise FilesystemPolicyError(f"File exceeds the {self.policy.max_read_bytes} byte read limit")
        return target.read_text(encoding="utf-8", errors="replace")

    def list_directory(self, path: str) -> list[dict[str, object]]:
        target = self.policy.resolve(path)
        if not target.is_dir():
            raise FilesystemPolicyError(f"Directory does not exist: {path}")
        return [
            {"name": item.name, "path": str(item), "is_directory": item.is_dir()}
            for item in sorted(target.iterdir(), key=lambda value: value.name.lower())
            if item.name.lower() not in self.policy.blocked_names
        ]

    def create_directory(self, path: str) -> str:
        target = self.policy.resolve(path)
        target.mkdir(parents=True, exist_ok=True)
        return str(target)

    def move(self, source: str, destination: str) -> str:
        source_path = self.policy.resolve(source)
        destination_path = self.policy.resolve(destination)
        if not source_path.exists():
            raise FilesystemPolicyError(f"Source does not exist: {source}")
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source_path), str(destination_path))
        return str(destination_path)

    def delete(self, path: str, recursive: bool = False) -> str:
        target = self.policy.resolve(path)
        if not target.exists():
            raise FilesystemPolicyError(f"Path does not exist: {path}")
        if target.is_dir():
            if not recursive:
                raise FilesystemPolicyError("Deleting a directory requires recursive=true")
            shutil.rmtree(target)
        else:
            target.unlink()
        return str(target)

    def metadata(self, path: str) -> dict[str, object]:
        target = self.policy.resolve(path)
        if not target.exists():
            raise FilesystemPolicyError(f"Path does not exist: {path}")
        stat = target.stat()
        return {
            "path": str(target),
            "name": target.name,
            "is_directory": target.is_dir(),
            "size_bytes": stat.st_size,
            "modified_at": stat.st_mtime,
        }
