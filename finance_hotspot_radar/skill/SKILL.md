---
name: finance-hotspot-radar
description: Use this skill when the user wants to discover, summarize, filter, or notify on finance market hotspots using the local finance-radar CLI and SQLite database. Supports keyword management, public-source scans, daily digests, alert notifications, and QQ/OneBot webhook configuration.
---

# Finance Hotspot Radar

Use the project CLI instead of reimplementing analysis logic.

## Quick workflow

1. Locate the project root that contains `pyproject.toml` and `finance_hotspot_radar/`.
2. Initialize if needed:
   ```bash
   python3 -m finance_hotspot_radar.cli --db ./radar.db init
   ```
3. Run a scan:
   ```bash
   python3 -m finance_hotspot_radar.cli --db ./radar.db scan
   ```
4. Produce a digest:
   ```bash
   python3 -m finance_hotspot_radar.cli --db ./radar.db digest --format text --hours 24 --limit 8
   ```

## Common commands

- Add a tracked topic:
  ```bash
  python3 -m finance_hotspot_radar.cli --db ./radar.db keyword add "英伟达" --aliases "NVIDIA,NVDA" --category us_equity --weight 1.3
  ```
- Pause a topic:
  ```bash
  python3 -m finance_hotspot_radar.cli --db ./radar.db keyword pause "英伟达"
  ```
- Search recent hotspots:
  ```bash
  python3 -m finance_hotspot_radar.cli --db ./radar.db search --keyword 央行 --sort importance --format table
  ```
- Send QQ/OneBot notification after environment variables are configured:
  ```bash
  python3 -m finance_hotspot_radar.cli --db ./radar.db digest --notify qq
  ```

## Interpretation rules

- Treat credibility as a risk signal, not as definitive fact checking.
- Mention source links and uncertainty when credibility is low.
- For user-facing summaries, prefer what changed, why it matters, affected assets/sectors, and what to keep watching.
