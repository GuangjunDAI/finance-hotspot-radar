from __future__ import annotations

import json
import urllib.request
from typing import Optional

from .base import Notifier


class WebhookNotifier(Notifier):
    channel = "webhook"

    def __init__(self, url: str, token: Optional[str] = None):
        self.url = url
        self.token = token

    def send(self, message: str) -> None:
        payload = {"text": message}
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(self.url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15):
            return


class OneBotNotifier(Notifier):
    channel = "qq-onebot"

    def __init__(self, url: str, target_type: str, target_id: str, access_token: Optional[str] = None):
        self.url = url.rstrip("/")
        self.target_type = target_type
        self.target_id = target_id
        self.access_token = access_token

    def send(self, message: str) -> None:
        action = "send_group_msg" if self.target_type == "group" else "send_private_msg"
        key = "group_id" if self.target_type == "group" else "user_id"
        payload = {key: int(self.target_id), "message": message}
        headers = {"Content-Type": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        req = urllib.request.Request(
            f"{self.url}/{action}",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15):
            return
