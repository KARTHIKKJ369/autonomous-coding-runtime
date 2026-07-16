from __future__ import annotations

from collections import defaultdict
from typing import Callable

from events.events import Event, EventType

Subscriber = Callable[[Event], None]


class EventBus:
    """In-process pub/sub. Handlers run synchronously in publish order."""

    def __init__(self) -> None:
        self._subs: dict[EventType, list[Subscriber]] = defaultdict(list)
        self._history: list[Event] = []

    def subscribe(self, event_type: EventType, handler: Subscriber) -> None:
        self._subs[event_type].append(handler)

    def publish(self, event: Event) -> None:
        self._history.append(event)
        for handler in self._subs.get(event.type, []):
            handler(event)

    @property
    def history(self) -> list[Event]:
        return list(self._history)
