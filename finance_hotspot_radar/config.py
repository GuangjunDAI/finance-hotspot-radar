from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


def load_env_file(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


load_env_file()


DEFAULT_DB_PATH = Path(os.environ.get("FINANCE_RADAR_DB", "~/.finance_hotspot_radar/radar.db")).expanduser()


DEFAULT_KEYWORDS = [
    ("宏观", "宏观,经济数据,GDP,CPI,PPI,PMI", "macro", 1.0),
    ("央行", "央行,降息,加息,货币政策,流动性,MLF,LPR,FOMC,美联储", "macro", 1.3),
    ("A股", "A股,上证,深证,创业板,北向资金,证监会", "cn_equity", 1.1),
    ("港股", "港股,恒生指数,南向资金,香港交易所", "hk_equity", 1.0),
    ("美股", "美股,纳斯达克,标普500,道琼斯,NVIDIA,Apple,Tesla", "us_equity", 1.1),
    ("汇率", "汇率,人民币,美元指数,离岸人民币,日元,欧元", "fx", 1.0),
    ("利率", "利率,国债收益率,美债,收益率曲线", "rates", 1.1),
    ("商品", "黄金,原油,铜,铁矿石,大宗商品,OPEC", "commodity", 1.0),
    ("加密", "比特币,BTC,以太坊,ETH,稳定币,ETF", "crypto", 1.0),
    ("重点公司", "财报,并购,回购,裁员,监管调查,破产,IPO", "company", 1.1),
]


@dataclass
class Settings:
    db_path: Path = DEFAULT_DB_PATH
    webhook_url: Optional[str] = os.environ.get("FINANCE_RADAR_WEBHOOK_URL")
    webhook_token: Optional[str] = os.environ.get("FINANCE_RADAR_WEBHOOK_TOKEN")
    qq_onebot_url: Optional[str] = os.environ.get("FINANCE_RADAR_QQ_ONEBOT_URL")
    qq_access_token: Optional[str] = os.environ.get("FINANCE_RADAR_QQ_ACCESS_TOKEN")
    qq_target_type: str = os.environ.get("FINANCE_RADAR_QQ_TARGET_TYPE", "group")
    qq_target_id: Optional[str] = os.environ.get("FINANCE_RADAR_QQ_TARGET_ID")
    ai_api_key: Optional[str] = os.environ.get("FINANCE_RADAR_AI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    ai_base_url: str = os.environ.get("FINANCE_RADAR_AI_BASE_URL", "https://api.openai.com/v1/chat/completions")
    ai_model: str = os.environ.get("FINANCE_RADAR_AI_MODEL", "gpt-4o-mini")
    user_agent: str = "finance-hotspot-radar/0.1 (+public-source-monitor)"

    def __post_init__(self) -> None:
        self.db_path = Path(self.db_path).expanduser()
        if self.ai_base_url and not self.ai_base_url.endswith("/chat/completions"):
            self.ai_base_url = self.ai_base_url.rstrip("/") + "/v1/chat/completions"


def default_rss_feeds() -> List[str]:
    env_feeds = os.environ.get("FINANCE_RADAR_RSS_FEEDS")
    if env_feeds:
        return [feed.strip() for feed in env_feeds.split(",") if feed.strip()]
    return [
        "https://news.google.com/rss/search?q=%E9%87%91%E8%9E%8D%20OR%20%E8%82%A1%E5%B8%82%20OR%20%E5%A4%AE%E8%A1%8C&hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=%5EDJI,%5EIXIC,%5EGSPC,BTC-USD,GC=F,CL=F&region=US&lang=en-US",
        "https://www.cls.cn/telegraph",
    ]
