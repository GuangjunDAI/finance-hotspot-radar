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
            hours = _int(qs, "hours", 24)
            limit = _int(qs, "limit", 20)
            source = _str(qs, "source")
            keyword = _str(qs, "keyword")
            min_importance = _float(qs, "min_importance", 0.0)
            sort = _str(qs, "sort") or "heat"
            order = _str(qs, "order") or "desc"
            hotspots = self._service().digest(
                hours=hours,
                limit=limit,
                source=source,
                keyword=keyword,
                min_importance=min_importance,
                sort=sort,
                order=order,
            )
            fallback_count = 0
            if not hotspots and hours < 168:
                fallback_count = len(
                    self._service().digest(
                        hours=168,
                        limit=limit,
                        source=source,
                        keyword=keyword,
                        min_importance=min_importance,
                        sort=sort,
                        order=order,
                    )
                )
            self._json({"items": [item.to_dict() for item in hotspots], "fallback_7d_count": fallback_count})
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
                order=_str(qs, "order") or "desc",
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
                order=str(body.get("order") or "desc"),
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
    :root {
      color-scheme: dark;
      --bg:#050807;
      --panel:rgba(10,18,17,.78);
      --panel-strong:rgba(15,28,26,.92);
      --ink:#e7f7f3;
      --muted:#8ea19b;
      --line:rgba(150,255,229,.16);
      --line-strong:rgba(150,255,229,.34);
      --accent:#27e0b3;
      --accent-2:#9cf6df;
      --warn:#f2c266;
      --risk:#ff6f8d;
      --shadow:0 20px 80px rgba(0,0,0,.35);
    }
    * { box-sizing: border-box; }
    body {
      margin:0;
      min-height:100vh;
      font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
      background:
        radial-gradient(circle at 18% 0%, rgba(39,224,179,.18), transparent 29rem),
        radial-gradient(circle at 82% 12%, rgba(242,194,102,.1), transparent 24rem),
        linear-gradient(180deg, #06100e 0%, #050807 46%, #07100f 100%);
      color:var(--ink);
    }
    body::before {
      content:"";
      position:fixed;
      inset:0;
      pointer-events:none;
      background-image:
        linear-gradient(rgba(156,246,223,.05) 1px, transparent 1px),
        linear-gradient(90deg, rgba(156,246,223,.045) 1px, transparent 1px);
      background-size:44px 44px;
      mask-image:radial-gradient(circle at 50% 8%, black, transparent 78%);
    }
    body::after {
      content:"";
      position:fixed;
      left:12%;
      right:12%;
      top:-180px;
      height:360px;
      pointer-events:none;
      background:radial-gradient(ellipse at center, rgba(156,246,223,.22), transparent 64%);
      filter:blur(28px);
    }
    header {
      position:sticky;
      top:0;
      z-index:10;
      padding:18px 28px;
      background:rgba(5,8,7,.72);
      border-bottom:1px solid var(--line);
      backdrop-filter:blur(18px);
      display:flex;
      justify-content:space-between;
      gap:16px;
      align-items:center;
    }
    h1 { font-size:22px; margin:0; letter-spacing:0; display:flex; align-items:center; gap:10px; }
    h1::before { content:""; width:10px; height:10px; border-radius:50%; background:var(--accent); box-shadow:0 0 24px var(--accent); }
    main { max-width:1420px; margin:0 auto; padding:24px; display:grid; grid-template-columns: 360px 1fr; gap:18px; position:relative; z-index:1; }
    section {
      position:relative;
      overflow:hidden;
      background:linear-gradient(180deg, rgba(15,28,26,.88), rgba(7,13,12,.82));
      border:1px solid var(--line);
      border-radius:12px;
      padding:18px;
      box-shadow:var(--shadow);
    }
    section::before {
      content:"";
      position:absolute;
      inset:0;
      pointer-events:none;
      background:linear-gradient(120deg, rgba(156,246,223,.11), transparent 28%, transparent 76%, rgba(242,194,102,.08));
      opacity:.72;
    }
    section > * { position:relative; z-index:1; }
    h2 { margin:0 0 14px; font-size:15px; letter-spacing:.02em; display:flex; align-items:center; justify-content:space-between; }
    h2::after { content:""; width:42px; height:1px; background:linear-gradient(90deg, var(--accent), transparent); }
    label { display:block; font-size:12px; color:var(--muted); margin:10px 0 5px; }
    input, select, button {
      width:100%;
      min-height:38px;
      border:1px solid var(--line);
      border-radius:8px;
      padding:8px 10px;
      font:inherit;
      background:rgba(255,255,255,.045);
      color:var(--ink);
      outline:none;
      transition:border-color .16s ease, box-shadow .16s ease, transform .16s ease, background .16s ease;
    }
    select option { color:#10201d; background:#f4fffc; }
    input:focus, select:focus { border-color:var(--line-strong); box-shadow:0 0 0 3px rgba(39,224,179,.12); }
    button {
      cursor:pointer;
      border-color:rgba(39,224,179,.52);
      color:#03120f;
      background:linear-gradient(135deg, var(--accent), var(--accent-2));
      font-weight:760;
    }
    button:hover { transform:translateY(-1px); box-shadow:0 10px 28px rgba(39,224,179,.18); }
    button.secondary { background:rgba(255,255,255,.035); color:var(--ink); border-color:var(--line-strong); }
    .row { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
    .toolbar { display:grid; grid-template-columns: repeat(6, minmax(100px,1fr)); gap:10px; margin-bottom:14px; align-items:end; }
    .status { font-size:12px; color:var(--muted); line-height:1.55; }
    .hero {
      grid-column:1 / -1;
      display:grid;
      grid-template-columns:minmax(0,1.25fr) minmax(320px,.75fr);
      gap:18px;
      align-items:stretch;
    }
    .hero-copy { padding:24px; }
    .eyebrow { color:var(--accent-2); font-size:12px; font-weight:750; letter-spacing:.12em; text-transform:uppercase; margin-bottom:10px; }
    .hero-title { margin:0; font-size:38px; line-height:1.08; letter-spacing:0; max-width:760px; }
    .hero-subtitle { margin:14px 0 0; color:var(--muted); line-height:1.7; max-width:760px; }
    .stats { display:grid; grid-template-columns:repeat(3, 1fr); gap:10px; margin-top:18px; }
    .stat {
      border:1px solid var(--line);
      background:rgba(255,255,255,.04);
      border-radius:10px;
      padding:12px;
    }
    .stat strong { display:block; font-size:22px; color:var(--accent-2); margin-bottom:2px; }
    .stat span { color:var(--muted); font-size:12px; }
    .signal-card {
      min-height:100%;
      display:flex;
      flex-direction:column;
      justify-content:space-between;
      background:
        radial-gradient(circle at 20% 20%, rgba(39,224,179,.2), transparent 16rem),
        linear-gradient(180deg, rgba(255,255,255,.055), rgba(255,255,255,.025));
    }
    .signal-line { height:86px; border-radius:10px; border:1px solid var(--line); background:linear-gradient(90deg, transparent, rgba(39,224,179,.12), transparent); position:relative; overflow:hidden; }
    .signal-line::before { content:""; position:absolute; inset:0; background:repeating-linear-gradient(90deg, transparent 0 22px, rgba(156,246,223,.2) 23px 24px); animation:drift 5s linear infinite; }
    @keyframes drift { to { transform:translateX(44px); } }
    .pill { display:inline-block; padding:4px 8px; border-radius:999px; background:rgba(39,224,179,.12); border:1px solid rgba(39,224,179,.18); color:var(--accent-2); font-size:12px; margin:0 5px 5px 0; }
    .hotspot {
      position:relative;
      margin-top:12px;
      border:1px solid var(--line);
      border-radius:12px;
      background:rgba(255,255,255,.035);
      padding:14px;
    }
    .hotspot::before { content:""; position:absolute; inset:-1px; border-radius:12px; padding:1px; background:linear-gradient(120deg, rgba(39,224,179,.45), transparent 32%, rgba(242,194,102,.28)); mask:linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0); mask-composite:exclude; pointer-events:none; opacity:.56; }
    .hotspot h3 { margin:0 0 8px; font-size:17px; line-height:1.38; }
    .meta { color:var(--muted); font-size:12px; margin-bottom:7px; line-height:1.55; }
    .risk { color:var(--risk); font-weight:700; }
    .keyword { display:flex; justify-content:space-between; gap:10px; align-items:center; border-top:1px solid var(--line); padding:10px 0; }
    .keyword button { width:auto; min-height:30px; padding:4px 10px; font-size:12px; color:var(--ink); }
    .digest { white-space:pre-wrap; background:rgba(0,0,0,.22); border:1px solid var(--line); border-radius:10px; padding:14px; max-height:420px; overflow:auto; font-size:13px; line-height:1.65; }
    .stack { display:grid; gap:14px; }
    .panel-title-row { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:10px; }
    .mini-badge { border:1px solid var(--line); background:rgba(255,255,255,.04); color:var(--muted); border-radius:999px; padding:5px 9px; font-size:12px; }
    a { color:var(--accent-2); text-decoration:none; word-break:break-all; }
    @media (max-width: 1080px) { main { grid-template-columns:1fr; } .hero { grid-template-columns:1fr; } .toolbar { grid-template-columns:1fr 1fr 1fr; } }
    @media (max-width: 720px) { main { padding:12px; } header { padding:14px; } .toolbar, .row, .stats { grid-template-columns:1fr; } .hero-title { font-size:30px; } }
  </style>
</head>
<body>
  <header>
    <h1>金融热点雷达</h1>
    <div id="config" class="status"></div>
  </header>
  <main>
    <section class="hero">
      <div class="hero-copy">
        <div class="eyebrow">Market Signal Console</div>
        <p class="hero-title">发现市场热点，过滤噪声，抓住正在升温的金融信号。</p>
        <p class="hero-subtitle">公开源扫描、关键词监控、AI 风险提示和本地筛选集中在一个轻量控制台里。保留速度和可读性，只把科技感加在该出现的地方。</p>
        <div class="stats">
          <div class="stat"><strong id="statHotspots">-</strong><span>当前结果</span></div>
          <div class="stat"><strong id="statKeywords">-</strong><span>监控关键词</span></div>
          <div class="stat"><strong id="statAi">-</strong><span>AI 状态</span></div>
        </div>
      </div>
      <div class="signal-card">
        <div>
          <h2>实时雷达</h2>
          <p class="status">扫描会把右侧筛选关键词作为本次临时监控词，适合临时追踪“医药”“机器人”“并购”等突然升温的话题。</p>
        </div>
        <div class="signal-line" aria-hidden="true"></div>
      </div>
    </section>
    <aside>
      <section class="moving-card">
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
    <div class="stack">
      <section>
        <div class="panel-title-row">
          <h2>热点筛选</h2>
          <span class="mini-badge">source · weight · time</span>
        </div>
        <div class="toolbar">
          <div><label>时间</label><select id="hours"><option value="6">6小时</option><option value="24" selected>24小时</option><option value="72">72小时</option><option value="168">7天</option></select></div>
          <div><label>来源</label><input id="source" placeholder="rss/google/weibo" /></div>
          <div><label>关键词</label><input id="keyword" placeholder="央行/美股" /></div>
          <div><label>重要性</label><input id="minImportance" type="number" step="0.5" value="0" /></div>
          <div><label>排序</label><select id="sort"><option value="heat">热度</option><option value="importance">重要性</option><option value="relevance">相关性</option><option value="time">时间</option></select></div>
          <div><label>顺序</label><select id="order"><option value="desc" selected>从大到小/最新</option><option value="asc">从小到大/最早</option></select></div>
          <div><label>数量</label><input id="limit" type="number" value="20" /></div>
        </div>
        <div class="row">
          <button id="refreshBtn">刷新热点</button>
          <button id="digestBtn" class="secondary">生成摘要</button>
        </div>
      </section>
      <section>
        <div class="panel-title-row">
          <h2>热点列表</h2>
          <span id="resultBadge" class="mini-badge">等待数据</span>
        </div>
        <div id="hotspots"></div>
      </section>
      <section>
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
      ['hours','source','keyword','sort','order','limit'].forEach(id => { if ($(id).value) q.set(id, $(id).value); });
      q.set('min_importance', $('minImportance').value || '0');
      return q.toString();
    }
    async function loadConfig() {
      const cfg = await api('/api/config');
      $('config').textContent = `DB ${cfg.db_path} · AI ${cfg.ai_enabled ? cfg.ai_model : 'off'} · QQ ${cfg.qq_configured ? 'configured' : 'reserved'}`;
      $('statAi').textContent = cfg.ai_enabled ? 'ON' : 'OFF';
    }
    async function loadKeywords() {
      const rows = await api('/api/keywords');
      $('statKeywords').textContent = rows.filter(kw => kw.active).length;
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
      let fallbackCount = 0;
      try {
        const payload = await api('/api/hotspots?' + params());
        rows = Array.isArray(payload) ? payload : payload.items || [];
        fallbackCount = Array.isArray(payload) ? 0 : payload.fallback_7d_count || 0;
      } catch (err) {
        $('hotspots').innerHTML = `<p class="risk">加载失败：${err.message}</p>`;
        $('resultBadge').textContent = '加载失败';
        return;
      }
      $('statHotspots').textContent = rows.length;
      $('resultBadge').textContent = rows.length ? `${rows.length} 条信号` : '暂无信号';
      const emptyHint = fallbackCount
        ? `<p class="status">当前时间窗没有命中，但 7 天内有 ${fallbackCount} 条相关信号。可把时间切到“7天”，或点“立即扫描公开源”拉取新数据。</p>`
        : '<p class="status">暂无热点。可先执行扫描；如果填了关键词，扫描会把它作为本次临时监控词。</p>';
      $('hotspots').innerHTML = rows.length ? rows.map(item => `
        <article class="hotspot">
          <h3>${item.title} ${item.status === 'risk' ? '<span class="risk">风险</span>' : ''}</h3>
          <div class="meta">重要性 ${item.importance} · 热度 ${item.heat} · 相关性 ${item.relevance} · 可信度 ${item.credibility} · ${item.published_at_display || item.published_at}</div>
          <div>${(item.keywords||[]).map(k => `<span class="pill">${k}</span>`).join('')}</div>
          <p>${item.summary || ''}</p>
          <p class="meta">${item.reason || ''}</p>
          ${(item.urls||[]).slice(0,3).map(u => `<a href="${u}" target="_blank">${u}</a>`).join('<br>')}
        </article>`).join('') : emptyHint;
    }
    async function loadDigest() {
      const data = await api('/api/digest?' + params());
      $('digest').textContent = data.text;
    }
    $('scanBtn').onclick = async () => {
      const btn = $('scanBtn');
      btn.disabled = true;
      btn.textContent = '扫描中...';
      $('scanStatus').textContent = '公开源和 AI 分析可能需要 40-90 秒，请稍等。';
      try {
        const data = await api('/api/scan', {method:'POST', body:JSON.stringify({no_social:$('noSocial').checked, keyword:$('keyword').value})});
        $('scanStatus').textContent = `保存 ${data.saved_hotspots} 条新热点`;
        await loadHotspots();
      } catch (err) {
        $('scanStatus').textContent = `扫描失败：${err.message}`;
      } finally {
        btn.disabled = false;
        btn.textContent = '立即扫描公开源';
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
