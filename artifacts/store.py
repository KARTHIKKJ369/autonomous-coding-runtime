from __future__ import annotations

from artifacts.artifact import Artifact, ArtifactType


class ArtifactStore:
    def __init__(self) -> None:
        self._items: dict[str, Artifact] = {}

    def add(self, type: ArtifactType, task_id: str, content: str, meta: dict | None = None) -> Artifact:
        artifact = Artifact(type=type, task_id=task_id, content=content, meta=meta or {})
        self._items[artifact.id] = artifact
        return artifact

    def get(self, artifact_id: str) -> Artifact | None:
        return self._items.get(artifact_id)

    def for_task(self, task_id: str) -> list[Artifact]:
        return [a for a in self._items.values() if a.task_id == task_id]

    def all(self) -> list[Artifact]:
        return list(self._items.values())
