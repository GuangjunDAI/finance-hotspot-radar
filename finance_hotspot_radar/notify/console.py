from __future__ import annotations

from .base import Notifier


class ConsoleNotifier(Notifier):
    channel = "console"

    def send(self, message: str) -> None:
        print(message)
