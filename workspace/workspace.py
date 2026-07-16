from __future__ import annotations

from pathlib import Path
from typing import Any

from filesystem.reader import FileReader
from filesystem.writer import FileWriter


class Workspace:
    """Single source of truth for filesystem state, plan, and scratchpad.
    No worker owns state; everything lives here on RuntimeState.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.reader = FileReader(self.root)
        self.writer = FileWriter(self.root)

        self.opened_files: set[str] = set()
        self.generated_files: set[str] = set()
        self.scratchpad: dict[str, Any] = {}
        self.execution_history: list[str] = []

    # --- file operations (record intent for context builder) ---
    def read_file(self, relative_path: str) -> str:
        self.opened_files.add(relative_path)
        content = self.reader.read(relative_path)
        self.execution_history.append(f"read {relative_path}")
        return content

    def write_file(self, relative_path: str, content: str) -> None:
        self.writer.write(relative_path, content)
        self.generated_files.add(relative_path)
        self.execution_history.append(f"wrote {relative_path}")

    def file_exists(self, relative_path: str) -> bool:
        return self.reader.exists(relative_path)

    def list_files(self, relative_path: str = ".") -> list[str]:
        return self.reader.list_dir(relative_path)

    def repository_tree(self, max_entries: int = 200) -> list[str]:
        return self.list_files()[:max_entries]

    # --- scratchpad ---
    def set_scratch(self, key: str, value: Any) -> None:
        self.scratchpad[key] = value

    def get_scratch(self, key: str, default: Any = None) -> Any:
        return self.scratchpad.get(key, default)
