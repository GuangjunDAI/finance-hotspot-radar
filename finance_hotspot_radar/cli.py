from __future__ import annotations

import argparse
import sys

from .config import DEFAULT_DB_PATH, Settings
from .formatter import digest_text, hotspots_json, hotspots_table, keywords_table
from .scheduler import run_scheduler
from .service import RadarService
from .storage import Store


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="finance-radar", description="Local finance hotspot radar")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Initialize database and seed default keywords")
    init.add_argument("--no-seed", action="store_true")

    scan = sub.add_parser("scan", help="Collect public sources and analyze hotspots")
    scan.add_argument("--no-social", action="store_true", help="Disable Weibo/Bilibili sources")

    digest = sub.add_parser("digest", help="Show digest from stored hotspots")
    _add_query_args(digest)
    digest.add_argument("--format", choices=["text", "table", "json"], default="text")
    digest.add_argument("--notify", choices=["console", "webhook", "qq", "qq-onebot"])

    alert = sub.add_parser("alert", help="Notify high-importance new hotspots")
    _add_query_args(alert)
    alert.add_argument("--channel", choices=["console", "webhook", "qq", "qq-onebot"], default="console")

    search = sub.add_parser("search", help="Search stored hotspots")
    _add_query_args(search)
    search.add_argument("--format", choices=["table", "json"], default="table")

    keyword = sub.add_parser("keyword", help="Manage keyword config")
    keyword_sub = keyword.add_subparsers(dest="keyword_command", required=True)
    keyword_sub.add_parser("list", help="List keywords").add_argument("--active-only", action="store_true")
    add = keyword_sub.add_parser("add", help="Add keyword")
    add.add_argument("name")
    add.add_argument("--aliases", default="", help="Comma-separated aliases")
    add.add_argument("--category", default="general")
    add.add_argument("--weight", type=float, default=1.0)
    add.add_argument("--paused", action="store_true")
    pause = keyword_sub.add_parser("pause", help="Pause keyword")
    pause.add_argument("name")
    activate = keyword_sub.add_parser("activate", help="Activate keyword")
    activate.add_argument("name")

    sched = sub.add_parser("schedule", help="Run simple local scheduler")
    sched.add_argument("--interval", type=int, default=3600, help="Scan interval seconds")
    sched.add_argument("--daily-time", default="08:30", help="Daily digest local HH:MM")
    sched.add_argument("--hours", type=int, default=24)
    sched.add_argument("--limit", type=int, default=8)
    sched.add_argument("--alert-importance", type=float, default=7.0)
    sched.add_argument("--channel", choices=["console", "webhook", "qq", "qq-onebot"], default="console")
    sched.add_argument("--no-social", action="store_true")

    web = sub.add_parser("web", help="Run local web dashboard")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8765)
    return parser


def _add_query_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--source")
    parser.add_argument("--keyword")
    parser.add_argument("--min-importance", type=float, default=0.0)
    parser.add_argument("--sort", choices=["heat", "relevance", "time", "importance"], default="heat")


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings(db_path=args.db)
    service = RadarService(settings)
    store = Store(settings.db_path)

    if args.command == "init":
        service.init_db(seed=not args.no_seed)
        print(f"Initialized {settings.db_path}")
        return 0
    if args.command == "scan":
        count = service.scan(include_social=not args.no_social)
        print(f"Saved {count} new hotspots")
        return 0
    if args.command in ("digest", "search", "alert"):
        hotspots = service.digest(args.hours, args.limit, args.source, args.keyword, args.min_importance, args.sort)
        if args.command == "alert":
            sent = service.notify_alerts(hotspots, args.channel, args.min_importance or 7.0)
            print(f"Sent {sent} alerts")
            return 0
        if getattr(args, "notify", None):
            service.notify_digest(hotspots, args.notify)
            return 0
        if args.format == "json":
            print(hotspots_json(hotspots))
        elif args.format == "table":
            print(hotspots_table(hotspots))
        else:
            print(digest_text(hotspots, title="金融热点雷达"))
        return 0
    if args.command == "keyword":
        store.init()
        if args.keyword_command == "list":
            print(keywords_table(store.list_keywords(active=True if args.active_only else None)))
        elif args.keyword_command == "add":
            aliases = [item.strip() for item in args.aliases.split(",") if item.strip()]
            store.add_keyword(args.name, aliases, args.category, args.weight, active=not args.paused)
            print(f"Added keyword {args.name}")
        elif args.keyword_command in ("pause", "activate"):
            updated = store.set_keyword_active(args.name, args.keyword_command == "activate")
            if not updated:
                print(f"Keyword not found: {args.name}", file=sys.stderr)
                return 1
            print(f"Updated keyword {args.name}")
        return 0
    if args.command == "schedule":
        run_scheduler(args)
        return 0
    if args.command == "web":
        from .web import run_web

        run_web(settings, host=args.host, port=args.port)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
