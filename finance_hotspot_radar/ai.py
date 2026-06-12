from __future__ import annotations

import json
import urllib.request
from typing import Dict, List, Optional

from .models import Hotspot, Keyword


class OpenAICompatibleProvider:
    """Small optional provider for OpenAI-compatible chat completions."""

    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    def expand_keywords(self, keywords: List[Keyword]) -> Optional[Dict[str, List[str]]]:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "Return compact JSON only. Expand Chinese finance monitoring keywords with aliases and related query terms.",
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        [{"name": kw.name, "aliases": kw.aliases, "category": kw.category} for kw in keywords],
                        ensure_ascii=False,
                    ),
                },
            ],
            "temperature": 0.2,
        }
        data = self._post(payload)
        try:
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return {str(key): [str(v) for v in values] for key, values in parsed.items() if isinstance(values, list)}
        except (KeyError, TypeError, ValueError):
            return None

    def annotate_hotspots(self, hotspots: List[Hotspot]) -> List[Hotspot]:
        if not hotspots:
            return hotspots
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return JSON array. For each finance hotspot, provide concise reason, credibility 0-1, "
                        "and status normal/risk. Do not claim unverified rumors as fact."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps([item.to_dict() for item in hotspots[:20]], ensure_ascii=False),
                },
            ],
            "temperature": 0.1,
        }
        data = self._post(payload)
        try:
            annotations = json.loads(data["choices"][0]["message"]["content"])
        except (KeyError, TypeError, ValueError):
            return hotspots
        for hotspot, annotation in zip(hotspots, annotations):
            if isinstance(annotation, dict):
                hotspot.reason = str(annotation.get("reason") or hotspot.reason)
                try:
                    hotspot.credibility = float(annotation.get("credibility", hotspot.credibility))
                except (TypeError, ValueError):
                    pass
                status = annotation.get("status")
                if status in ("normal", "risk"):
                    hotspot.status = status
        return hotspots

    def _post(self, payload: dict) -> dict:
        req = urllib.request.Request(
            self.base_url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
