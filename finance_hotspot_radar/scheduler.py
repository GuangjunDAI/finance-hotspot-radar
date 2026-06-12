from __future__ import annotations

import argparse
import time
from datetime import datetime

from .config import Settings
from .service import RadarService


def run_scheduler(args: argparse.Namespace) -> None:
    service = RadarService(Settings(db_path=args.db))
    last_daily = ""
    while True:
        now = datetime.now()
        try:
            service.scan(include_social=not args.no_social)
            hotspots = service.digest(hours=args.hours, limit=args.limit, min_importance=args.alert_importance, sort="importance")
            service.notify_alerts(hotspots, channel=args.channel, min_importance=args.alert_importance)
            marker = now.strftime("%Y-%m-%d %H:%M")
            if now.strftime("%H:%M") == args.daily_time and marker != last_daily:
                daily = service.digest(hours=24, limit=args.limit, sort="heat")
                service.notify_digest(daily, channel=args.channel, title="每日金融热点雷达")
                last_daily = marker
        except Exception as exc:
            print(f"[scheduler] {exc}")
        time.sleep(args.interval)
