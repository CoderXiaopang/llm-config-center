from dataclasses import dataclass, field
from time import time


@dataclass
class ConfigCache:
    items: dict[str, object] = field(default_factory=dict)
    version: int | None = None
    last_checked_at: float = 0

    def clear(self) -> None:
        self.items.clear()

    def should_check(self, refresh_interval: int) -> bool:
        return time() - self.last_checked_at >= refresh_interval

    def mark_checked(self) -> None:
        self.last_checked_at = time()

