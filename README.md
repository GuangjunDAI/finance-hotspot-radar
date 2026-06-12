# Finance Hotspot Radar

本地金融热点雷达：从公开来源抓取金融/社媒热点，写入 SQLite，进行关键词匹配、热度/重要性/可信度评分，并支持每日摘要和突发通知。

## Quick start

推荐使用项目虚拟环境启动：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e .
finance-radar --db ./radar.db init
finance-radar --db ./radar.db keyword list
finance-radar --db ./radar.db scan
finance-radar --db ./radar.db digest --format text
```

如果你不想安装命令行入口，也可以直接用模块方式运行：

```bash
python3 -m finance_hotspot_radar.cli --db ./radar.db init
python3 -m finance_hotspot_radar.cli --db ./radar.db keyword list
python3 -m finance_hotspot_radar.cli --db ./radar.db scan
python3 -m finance_hotspot_radar.cli --db ./radar.db digest --format text
```

## 启动 Web dashboard

```bash
source .venv/bin/activate
finance-radar --db ./radar.db web --host 127.0.0.1 --port 8765
```

如果 `8765` 已被占用，可以换一个端口，例如：

```bash
finance-radar --db ./radar.db web --host 127.0.0.1 --port 8766
```

## Commands

- `init`：初始化 SQLite，并写入默认金融关键词。
- `scan`：抓取公开来源并分析热点。
- `digest`：输出每日摘要，可加 `--notify console|webhook|qq`。
- `alert`：只推送高重要性热点，默认用通知记录防重复。
- `search`：按来源、关键词、时间、重要性筛选并排序。
- `keyword add|pause|activate|list`：管理关键词和激活状态。
- `schedule`：运行本地循环调度，支持每日摘要和突发扫描。
- `web`：启动本地监控 Web 页面。

## Web dashboard

```bash
python3 -m finance_hotspot_radar.cli --db ./radar.db web --host 127.0.0.1 --port 8765
```

打开 `http://127.0.0.1:8765` 后可以：

- 手动扫描公开源。
- 按来源、关键词、重要性、时间范围筛选热点。
- 按热度、相关性、时间、重要性排序。
- 新增关键词，并暂停/激活监控项。
- 预览每日摘要。

## Notification config

Webhook:

```bash
export FINANCE_RADAR_WEBHOOK_URL="https://example.com/webhook"
export FINANCE_RADAR_WEBHOOK_TOKEN="optional-token"
```

QQ OneBot/NapCat:

```bash
export FINANCE_RADAR_QQ_ONEBOT_URL="http://127.0.0.1:3000"
export FINANCE_RADAR_QQ_TARGET_TYPE="group" # group or private
export FINANCE_RADAR_QQ_TARGET_ID="123456"
export FINANCE_RADAR_QQ_ACCESS_TOKEN="optional-token"
finance-radar --db ./radar.db digest --notify qq
```

Optional AI provider:

```bash
export FINANCE_RADAR_AI_API_KEY="..."
export FINANCE_RADAR_AI_BASE_URL="https://api.openai.com/v1/chat/completions"
export FINANCE_RADAR_AI_MODEL="gpt-4o-mini"
```

`FINANCE_RADAR_AI_BASE_URL` 可以填完整 `/v1/chat/completions`，也可以只填域名，程序会自动补齐路径。未配置 AI key 时会自动使用本地启发式分析器；配置后会额外做关键词扩展和可信度/风险说明润色。

## Source policy

第一版只使用公开可访问来源。Google 使用 Google News RSS；微博/B站使用公开接口；RSS 源可通过 `FINANCE_RADAR_RSS_FEEDS` 逗号分隔配置。

真伪判断是“可信度和风险提示”，不会把单一来源传闻当成确定事实。
