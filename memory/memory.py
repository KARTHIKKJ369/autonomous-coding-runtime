from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MemoryEntry:
    key: str
    value: str
    tags: list[str] = field(default_factory=list)


class MemoryStore:
    """Retrieval-based memory. Never inject everything - retrieve only relevant entries.

    Simple keyword-overlap retrieval by default; swap `retrieve` for embedding-based
    search later without changing the interface skills/executive depend on.
    """

    def __init__(self) -> None:
        self.short_term: list[MemoryEntry] = []  # current execution/session
        self.workspace_memory: list[MemoryEntry] = []  # repo knowledge, architecture, deps
        self.long_term: list[MemoryEntry] = []  # user prefs, coding style, conventions

    def add_short_term(self, key: str, value: str, tags: list[str] | None = None) -> None:
        self.short_term.append(MemoryEntry(key, value, tags or []))

    def add_workspace(self, key: str, value: str, tags: list[str] | None = None) -> None:
        self.workspace_memory.append(MemoryEntry(key, value, tags or []))

    def add_long_term(self, key: str, value: str, tags: list[str] | None = None) -> None:
        self.long_term.append(MemoryEntry(key, value, tags or []))

    def retrieve(self, query: str, k: int = 5) -> list[MemoryEntry]:
        query_terms = set(query.lower().split())
        pool = self.short_term + self.workspace_memory + self.long_term

        def score(entry: MemoryEntry) -> int:
            text = (entry.key + " " + entry.value + " " + " ".join(entry.tags)).lower()
            return sum(1 for term in query_terms if term in text)

        scored = [(score(e), e) for e in pool]
        scored = [pair for pair in scored if pair[0] > 0]
        scored.sort(key=lambda pair: -pair[0])
        return [e for _, e in scored[:k]]
