from __future__ import annotations

import json
from typing import Iterable, List

from .models import Hotspot, Keyword


def hotspots_json(hotspots: Iterable[Hotspot]) -> str:
    return json.dumps([item.to_dict() for item in hotspots], ensure_ascii=False, indent=2)


def hotspots_table(hotspots: Iterable[Hotspot]) -> str:
    rows = list(hotspots)
    if not rows:
        return "No hotspots found."
    lines = ["ID  Imp  Heat  Cred  Time                 Title"]
    for item in rows:
        item_id = item.id if item.id is not None else "-"
        lines.append(
            f"{str(item_id):<3} {item.importance:>4.1f} {item.heat:>5.1f} {item.credibility:>5.2f} "
            f"{item.published_at.strftime('%Y-%m-%d %H:%M'):<20} {item.title[:80]}"
        )
    return "\n".join(lines)


def keywords_table(keywords: List[Keyword]) -> str:
    if not keywords:
        return "No keywords configured."
    lines = ["ID  Active  Weight  Category      Name / aliases"]
    for kw in keywords:
        aliases = ", ".join(kw.aliases)
        lines.append(f"{kw.id:<3} {str(kw.active):<6} {kw.weight:>6.2f}  {kw.category:<12} {kw.name} ({aliases})")
    return "\n".join(lines)


def digest_text(hotspots: List[Hotspot], title: str = "金融热点雷达") -> str:
    if not hotspots:
        return f"{title}\n\n过去时间窗内没有发现达到阈值的新热点。"
    lines = [title, ""]
    for idx, item in enumerate(hotspots, start=1):
        risk = " [可信度风险]" if item.status == "risk" else ""
        lines.append(f"{idx}. {item.title}{risk}")
        lines.append(
            f"   重要性 {item.importance:.1f} / 热度 {item.heat:.1f} / 可信度 {item.credibility:.2f}；"
            f"来源：{', '.join(item.sources) or '未知'}"
        )
        if item.summary and item.summary != item.title:
            lines.append(f"   摘要：{item.summary[:180]}")
        lines.append(f"   观察信号：{item.reason}")
        if item.urls:
            lines.append(f"   链接：{item.urls[0]}")
    lines.append("")
    lines.append("值得继续盯的变化：高重要性低可信度事件、同主题多来源新增报道、热度持续上升的关键词。")
    return "\n".join(lines)
