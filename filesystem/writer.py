from __future__ import annotations

from pathlib import Path

from filesystem.reader import FileReader


class FileWriter:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._reader = FileReader(root)

    def write(self, relative_path: str, content: str) -> None:
        path = self._reader._resolve(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def delete(self, relative_path: str) -> None:
        path = self._reader._resolve(relative_path)
        if path.exists():
            path.unlink()

    def rename(self, src: str, dst: str) -> None:
        src_path = self._reader._resolve(src)
        dst_path = self._reader._resolve(dst)
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        src_path.rename(dst_path)

    def move(self, src: str, dst: str) -> None:
        self.rename(src, dst)
