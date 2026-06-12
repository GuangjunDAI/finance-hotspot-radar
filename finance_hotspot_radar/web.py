from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict
from urllib.parse import parse_qs, urlparse

from .config import Settings
from .formatter import digest_text
from .service import RadarService
from .storage import Store


def run_web(settings: Settings, host: str = "127.0.0.1", port: int = 8765) -> None:
    RadarService(settings).init_db(seed=True)

    class Handler(RadarRequestHandler):
        radar_settings = settings

    server = HTTPServer((host, port), Handler)
    print(f"Finance Hotspot Radar web dashboard: http://{host}:{port}")
    server.serve_forever()


class RadarRequestHandler(BaseHTTPRequestHandler):
    radar_settings: Settings

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._html(INDEX_HTML)
            return
        if parsed.path == "/api/config":
            self._json(
                {
                    "db_path": str(self.radar_settings.db_path),
                    "ai_enabled": bool(self.radar_settings.ai_api_key),
                    "ai_base_url": self.radar_settings.ai_base_url,
                    "ai_model": self.radar_settings.ai_model,
                    "qq_configured": bool(self.radar_settings.qq_onebot_url and self.radar_settings.qq_target_id),
                }
            )
            return
        if parsed.path == "/api/keywords":
            store = Store(self.radar_settings.db_path)
            store.init()
            self._json([kw.__dict__ for kw in store.list_keywords()])
            return
        if parsed.path == "/api/hotspots":
            qs = parse_qs(parsed.query)
            hotspots = self._service().digest(
                hours=_int(qs, "hours", 24),
                limit=_int(qs, "limit", 20),
                source=_str(qs, "source"),
                keyword=_str(qs, "keyword"),
                min_importance=_float(qs, "min_importance", 0.0),
                sort=_str(qs, "sort") or "heat",
            )
            self._json([item.to_dict() for item in hotspots])
            return
        if parsed.path == "/api/digest":
            qs = parse_qs(parsed.query)
            hotspots = self._service().digest(
                hours=_int(qs, "hours", 24),
                limit=_int(qs, "limit", 8),
                source=_str(qs, "source"),
                keyword=_str(qs, "keyword"),
                min_importance=_float(qs, "min_importance", 0.0),
                sort=_str(qs, "sort") or "heat",
            )
            self._json({"text": digest_text(hotspots, title="金融热点雷达")})
            return
        self.send_error(404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/scan":
            body = self._body()
            count = self._service().scan(
                include_social=not body.get("no_social", False),
                extra_keyword=str(body.get("keyword") or "").strip() or None,
            )
            self._json({"saved_hotspots": count})
            return
        if parsed.path == "/api/keywords":
            body = self._body()
            name = str(body.get("name") or "").strip()
            if not name:
                self._json({"error": "name is required"}, status=400)
                return
            aliases = body.get("aliases") or []
            if isinstance(aliases, str):
                aliases = [item.strip() for item in aliases.split(",") if item.strip()]
            store = Store(self.radar_settings.db_path)
            store.init()
            store.add_keyword(
                name=name,
                aliases=aliases,
                category=str(body.get("category") or "general"),
                weight=float(body.get("weight") or 1.0),
                active=bool(body.get("active", True)),
            )
            self._json({"ok": True})
            return
        if parsed.path == "/api/keywords/state":
            body = self._body()
            name = str(body.get("name") or "").strip()
            active = bool(body.get("active"))
            store = Store(self.radar_settings.db_path)
            store.init()
            updated = store.set_keyword_active(name, active)
            self._json({"ok": bool(updated), "updated": updated})
            return
        if parsed.path == "/api/notify/digest":
            body = self._body()
            hotspots = self._service().digest(
                hours=int(body.get("hours") or 24),
                limit=int(body.get("limit") or 8),
                min_importance=float(body.get("min_importance") or 0.0),
                sort=str(body.get("sort") or "heat"),
            )
            channel = str(body.get("channel") or "console")
            sent = self._service().notify_digest(hotspots, channel=channel)
            self._json({"sent": sent})
            return
        self.send_error(404)

    def _service(self) -> RadarService:
        return RadarService(self.radar_settings)

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _json(self, value: Any, status: int = 200) -> None:
        data = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _html(self, value: str) -> None:
        data = value.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _str(qs: Dict[str, list], key: str) -> str:
    return (qs.get(key) or [""])[0]


def _int(qs: Dict[str, list], key: str, default: int) -> int:
    try:
        return int(_str(qs, key) or default)
    except ValueError:
        return default


def _float(qs: Dict[str, list], key: str, default: float) -> float:
    try:
        return float(_str(qs, key) or default)
    except ValueError:
        return default


INDEX_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>金融热点雷达</title>
  <style>
    :root { color-scheme: light; --bg:#f6f7f9; --panel:#ffffff; --ink:#1d2430; --muted:#657184; --line:#dfe4ea; --accent:#126c5f; --warn:#a24614; --risk:#9f2436; }
    * { box-sizing: border-box; }
    body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; background:var(--bg); color:var(--ink); }
    header { padding:18px 28px; background:#10231f; color:white; display:flex; justify-content:space-between; gap:16px; align-items:center; }
    h1 { font-size:22px; margin:0; letter-spacing:0; }
    main { max-width:1280px; margin:0 auto; padding:22px; display:grid; grid-template-columns: 330px 1fr; gap:18px; }
    section { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:16px; }
    h2 { margin:0 0 12px; font-size:16px; }
    label { display:block; font-size:12px; color:var(--muted); margin:10px 0 4px; }
    input, select, button { width:100%; min-height:36px; border:1px solid var(--line); border-radius:6px; padding:7px 9px; font:inherit; background:white; color:var(--ink); }
    button { cursor:pointer; background:var(--accent); border-color:var(--accent); color:white; font-weight:650; }
    button.secondary { background:white; color:var(--ink); }
    .row { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
    .toolbar { display:grid; grid-template-columns: repeat(6, minmax(96px,1fr)); gap:8px; margin-bottom:12px; align-items:end; }
    .status { font-size:12px; color:var(--muted); }
    .pill { display:inline-block; padding:3px 7px; border-radius:999px; background:#eef4f2; color:#14584f; font-size:12px; margin-right:4px; }
    .hotspot { border-top:1px solid var(--line); padding:13px 0; }
    .hotspot:first-child { border-top:0; }
    .hotspot h3 { margin:0 0 6px; font-size:17px; line-height:1.35; }
    .meta { color:var(--muted); font-size:12px; margin-bottom:6px; }
    .risk { color:var(--risk); font-weight:700; }
    .keyword { display:flex; justify-content:space-between; gap:8px; align-items:center; border-top:1px solid var(--line); padding:8px 0; }
    .keyword button { width:auto; min-height:30px; padding:4px 9px; font-size:12px; }
    .digest { white-space:pre-wrap; background:#f8fafb; border:1px solid var(--line); border-radius:6px; padding:12px; max-height:420px; overflow:auto; font-size:13px; line-height:1.55; }
    a { color:#0f5f95; text-decoration:none; }
    @media (max-width: 900px) { main { grid-template-columns:1fr; padding:12px; } .toolbar { grid-template-columns:1fr 1fr; } header { padding:14px; } }
  </style>
</head>
<body>
  <header>
    <h1>金融热点雷达</h1>
    <div id="config" class="status"></div>
  </header>
  <main>
    <aside>
      <section>
        <h2>扫描控制</h2>
        <button id="scanBtn">立即扫描公开源</button>
        <label><input id="noSocial" type="checkbox" style="width:auto;min-height:auto"> 不扫描微博/B站</label>
        <p id="scanStatus" class="status">扫描会把右侧筛选关键词作为本次临时监控词。</p>
      </section>
      <section style="margin-top:14px">
        <h2>新增关键词</h2>
        <label>关键词</label><input id="kwName" placeholder="例如：英伟达" />
        <label>别名</label><input id="kwAliases" placeholder="NVIDIA,NVDA" />
        <div class="row">
          <div><label>分类</label><input id="kwCategory" value="general" /></div>
          <div><label>权重</label><input id="kwWeight" type="number" step="0.1" value="1.0" /></div>
        </div>
        <button id="addKwBtn" style="margin-top:10px">添加关键词</button>
      </section>
      <section style="margin-top:14px">
        <h2>关键词开关</h2>
        <div id="keywords"></div>
      </section>
    </aside>
    <div>
      <section>
        <h2>热点筛选</h2>
        <div class="toolbar">
          <div><label>时间</label><select id="hours"><option value="6">6小时</option><option value="24" selected>24小时</option><option value="72">72小时</option><option value="168">7天</option></select></div>
          <div><label>来源</label><input id="source" placeholder="rss/google/weibo" /></div>
          <div><label>关键词</label><input id="keyword" placeholder="央行/美股" /></div>
          <div><label>重要性</label><input id="minImportance" type="number" step="0.5" value="0" /></div>
          <div><label>排序</label><select id="sort"><option value="heat">热度</option><option value="importance">重要性</option><option value="relevance">相关性</option><option value="time">时间</option></select></div>
          <div><label>数量</label><input id="limit" type="number" value="20" /></div>
        </div>
        <div class="row">
          <button id="refreshBtn">刷新热点</button>
          <button id="digestBtn" class="secondary">生成摘要</button>
        </div>
      </section>
      <section style="margin-top:14px">
        <h2>热点列表</h2>
        <div id="hotspots"></div>
      </section>
      <section style="margin-top:14px">
        <h2>摘要预览</h2>
        <div id="digest" class="digest">点击“生成摘要”查看。</div>
      </section>
    </div>
  </main>
  <script>
    const $ = id => document.getElementById(id);
    const api = async (url, options={}) => {
      const res = await fetch(url, {headers:{'Content-Type':'application/json'}, ...options});
      const text = await res.text();
      let data;
      try { data = text ? JSON.parse(text) : {}; } catch { data = {error:text || res.statusText}; }
      if (!res.ok) throw new Error(data.error || res.statusText);
      return data;
    };
    function params() {
      const q = new URLSearchParams();
      ['hours','source','keyword','sort','limit'].forEach(id => { if ($(id).value) q.set(id, $(id).value); });
      q.set('min_importance', $('minImportance').value || '0');
      return q.toString();
    }
    async function loadConfig() {
      const cfg = await api('/api/config');
      $('config').textContent = `DB ${cfg.db_path} · AI ${cfg.ai_enabled ? cfg.ai_model : 'off'} · QQ ${cfg.qq_configured ? 'configured' : 'reserved'}`;
    }
    async function loadKeywords() {
      const rows = await api('/api/keywords');
      $('keywords').innerHTML = rows.map(kw => `
        <div class="keyword">
          <div><strong>${kw.name}</strong><br><span class="status">${kw.category} · ${kw.weight} · ${(kw.aliases||[]).join(', ')}</span></div>
          <button class="secondary" onclick="setKeyword('${kw.name.replaceAll("'", "\\'")}', ${!kw.active})">${kw.active ? '暂停' : '激活'}</button>
        </div>`).join('');
    }
    async function setKeyword(name, active) {
      await api('/api/keywords/state', {method:'POST', body:JSON.stringify({name, active})});
      await loadKeywords();
    }
    async function loadHotspots() {
      let rows = [];
      try {
        rows = await api('/api/hotspots?' + params());
      } catch (err) {
        $('hotspots').innerHTML = `<p class="risk">加载失败：${err.message}</p>`;
        return;
      }
      $('hotspots').innerHTML = rows.length ? rows.map(item => `
        <article class="hotspot">
          <h3>${item.title} ${item.status === 'risk' ? '<span class="risk">风险</span>' : ''}</h3>
          <div class="meta">重要性 ${item.importance} · 热度 ${item.heat} · 相关性 ${item.relevance} · 可信度 ${item.credibility} · ${item.published_at}</div>
          <div>${(item.keywords||[]).map(k => `<span class="pill">${k}</span>`).join('')}</div>
          <p>${item.summary || ''}</p>
          <p class="meta">${item.reason || ''}</p>
          ${(item.urls||[]).slice(0,3).map(u => `<a href="${u}" target="_blank">${u}</a>`).join('<br>')}
        </article>`).join('') : '<p class="status">暂无热点。可先执行扫描。</p>';
    }
    async function loadDigest() {
      const data = await api('/api/digest?' + params());
      $('digest').textContent = data.text;
    }
    $('scanBtn').onclick = async () => {
      $('scanStatus').textContent = '扫描中...';
      try {
        const data = await api('/api/scan', {method:'POST', body:JSON.stringify({no_social:$('noSocial').checked, keyword:$('keyword').value})});
        $('scanStatus').textContent = `保存 ${data.saved_hotspots} 条新热点`;
        await loadHotspots();
      } catch (err) {
        $('scanStatus').textContent = `扫描失败：${err.message}`;
      }
    };
    $('addKwBtn').onclick = async () => {
      await api('/api/keywords', {method:'POST', body:JSON.stringify({name:$('kwName').value, aliases:$('kwAliases').value, category:$('kwCategory').value, weight:$('kwWeight').value, active:true})});
      $('kwName').value = ''; $('kwAliases').value = '';
      await loadKeywords();
    };
    $('refreshBtn').onclick = loadHotspots;
    $('digestBtn').onclick = loadDigest;
    loadConfig(); loadKeywords(); loadHotspots();
  </script>
</body>
</html>"""
