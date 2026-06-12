from __future__ import annotations

from abc import ABC, abstractmethod


class Notifier(ABC):
    channel = "unknown"

    @abstractmethod
    def send(self, message: str) -> None:
        raise NotImplementedError
