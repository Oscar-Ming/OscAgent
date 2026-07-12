from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from oscagent.actions import PendingOperation
from oscagent.tools.workspace import resolve_workspace_path

MAX_PLANNED_OPERATIONS = 20


@dataclass(frozen=True)
class FileOrganizationPlan:
    description: str
    operations: list[PendingOperation]
    matched_count: int


class FileOrganizerPlanner:
    def __init__(self, workspace_root: Path, max_operations: int = MAX_PLANNED_OPERATIONS) -> None:
        self._workspace_root = workspace_root
        self._max_operations = max_operations

    def plan(self, prompt: str) -> FileOrganizationPlan | None:
        parsed = self._parse_prompt(prompt.strip())
        if not parsed:
            return None

        extension, source, destination = parsed
        source_path = resolve_workspace_path(self._workspace_root, source)
        destination_path = resolve_workspace_path(self._workspace_root, destination)

        if not source_path.exists():
            raise FileNotFoundError(f"Source directory does not exist: {source}")
        if not source_path.is_dir():
            raise ValueError(f"Source path is not a directory: {source}")

        matching_files = [
            path
            for path in sorted(source_path.iterdir())
            if path.is_file()
            and path.suffix.lower() == extension
            and path.parent.resolve() != destination_path.resolve()
        ]
        selected_files = matching_files[: self._max_operations]

        operations = [
            PendingOperation(
                "move_file",
                {
                    "source": self._relative_workspace_path(path),
                    "destination": self._relative_workspace_path(destination_path / path.name),
                },
            )
            for path in selected_files
        ]

        suffix = ""
        if len(matching_files) > len(selected_files):
            suffix = f" (first {len(selected_files)} of {len(matching_files)} files)"

        return FileOrganizationPlan(
            description=(
                f"Organize {extension.lstrip('.')} files from `{source}` "
                f"to `{destination}`{suffix}"
            ),
            operations=operations,
            matched_count=len(matching_files),
        )

    def _parse_prompt(self, prompt: str) -> tuple[str, str, str] | None:
        patterns = (
            r"^organize\s+\.?([a-z0-9]+)\s+files\s+in\s+(.+?)\s+to\s+(.+)$",
            r"^move\s+all\s+\.?([a-z0-9]+)\s+files\s+from\s+(.+?)\s+to\s+(.+)$",
            (
                r"^\u628a\s+(.+?)\s+\u91cc(?:\u7684)?\s+\.?([a-z0-9]+)"
                r"\s+\u6587\u4ef6\s*(?:\u6574\u7406|\u79fb\u52a8)\u5230\s+(.+)$"
            ),
        )
        for pattern in patterns:
            match = re.match(pattern, prompt, flags=re.IGNORECASE)
            if not match:
                continue
            if pattern.startswith(r"^\u628a"):
                source, extension, destination = match.groups()
            else:
                extension, source, destination = match.groups()
            return (
                self._normalize_extension(extension),
                self._clean_path(source),
                self._clean_path(destination),
            )
        return None

    def _normalize_extension(self, extension: str) -> str:
        cleaned = extension.strip().lower().lstrip(".")
        if not re.fullmatch(r"[a-z0-9]+", cleaned):
            raise ValueError(f"Unsupported file extension: {extension}")
        return f".{cleaned}"

    def _clean_path(self, path: str) -> str:
        return path.strip().strip("`'\"")

    def _relative_workspace_path(self, path: Path) -> str:
        return path.resolve().relative_to(self._workspace_root.resolve()).as_posix()
