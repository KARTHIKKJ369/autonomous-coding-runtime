from __future__ import annotations

from pathlib import Path


class FileReader:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _resolve(self, relative_path: str) -> Path:
        p = (self.root / relative_path).resolve()
        if not str(p).startswith(str(self.root)):
            raise PermissionError(f"Path escapes workspace root: {relative_path}")
        return p

    def read(self, relative_path: str) -> str:
        path = self._resolve(relative_path)
        if not path.exists():
            raise FileNotFoundError(relative_path)
        return path.read_text(encoding="utf-8", errors="replace")

    def exists(self, relative_path: str) -> bool:
        try:
            return self._resolve(relative_path).exists()
        except PermissionError:
            return False

    def list_dir(self, relative_path: str = ".") -> list[str]:
        path = self._resolve(relative_path)
        if not path.exists():
            return []
        return sorted(str(p.relative_to(self.root)) for p in path.rglob("*") if p.is_file())
