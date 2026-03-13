from __future__ import annotations

import json
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse


HTML = '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ARC Influence Queue</title>
<style>
:root{--bg:#0f1017;--panel:#171925;--panel2:#1d2030;--text:#f3ecff;--muted:#b8a9d8;--accent:#8a63ff;--line:#302a46;--ok:#2f8f57;--warn:#c48f1f;--bad:#a84545}
*{box-sizing:border-box} body{margin:0;font-family:Inter,Arial,sans-serif;background:var(--bg);color:var(--text)}
.wrap{display:grid;grid-template-columns:380px 1fr;min-height:100vh}
.sidebar{border-right:1px solid var(--line);background:var(--panel);padding:16px;overflow:auto}
.main{padding:16px;overflow:auto}
button{background:var(--accent);border:none;color:white;padding:10px 14px;border-radius:12px;cursor:pointer}
button.secondary{background:#26283a} button.good{background:var(--ok)} button.warn{background:var(--warn)} button.bad{background:var(--bad)}
input,select,textarea{width:100%;background:var(--panel2);border:1px solid var(--line);color:var(--text);border-radius:12px;padding:10px}
textarea{min-height:220px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.card{padding:12px;border:1px solid var(--line);border-radius:14px;margin:10px 0;background:var(--panel2)}
.card.active{outline:2px solid var(--accent)} .muted{color:var(--muted)} .row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.pill{padding:4px 8px;border-radius:999px;background:#27243a;color:#d8c8ff;font-size:12px} .grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
pre{white-space:pre-wrap;background:var(--panel2);padding:12px;border-radius:12px;border:1px solid var(--line)}
</style>
</head>
<body>
<div class="wrap">
  <aside class="sidebar">
    <div class="row"><h2 style="margin:0">Queue</h2><button class="secondary" onclick="loadQueue()">Refresh</button></div>
    <p class="muted">Review, edit, approve, and optionally publish staged packets.</p>
    <input id="filter" placeholder="Filter by repo/outlet/status" oninput="renderList()">
    <div id="list"></div>
  </aside>
  <main class="main">
    <div class="row" style="justify-content:space-between"><h1 style="margin:0">ARC Influence Operator</h1><span class="muted" id="status">No item selected</span></div>
    <div id="detail" class="muted" style="margin-top:14px">Select a staged packet on the left.</div>
  </main>
</div>
<script>
let queue=[]; let current=null; let currentData=null;
function esc(s){return (s??'').toString().replace(/[&<>\"]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]))}
async function loadQueue(){ const r=await fetch('/api/queue'); queue=await r.json(); renderList(); if(current){ const found=queue.find(x=>x.id===current); if(found){ loadItem(current); } } }
function renderList(){ const q=document.getElementById('filter').value.toLowerCase(); const el=document.getElementById('list'); el.innerHTML=''; for(const item of queue){ const hay=[item.repo,item.outlet,item.destination,item.status].join(' ').toLowerCase(); if(q && !hay.includes(q)) continue; const div=document.createElement('div'); div.className='card'+(item.id===current?' active':''); div.onclick=()=>loadItem(item.id); div.innerHTML=`<div class=row><strong>${esc(item.repo)}</strong><span class=pill>${esc(item.outlet)}</span></div><div class=muted>${esc(item.destination||'default')}</div><div class=row><span class=pill>${esc(item.status)}</span><span class=pill>${item.approved?'approved':'unapproved'}</span></div>`; el.appendChild(div);} }
async function loadItem(id){ current=id; const r=await fetch('/api/item?id='+encodeURIComponent(id)); currentData=await r.json(); document.getElementById('status').textContent=currentData.repo+' · '+currentData.outlet; renderList(); renderDetail(); }
function renderDetail(){ if(!currentData){ return; } const d=currentData; const detail=document.getElementById('detail'); detail.className=''; detail.innerHTML=`
  <div class=grid2>
    <div><label>Title</label><input id=title value="${esc(d.title)}"></div>
    <div><label>Destination</label><input id=destination value="${esc(d.destination||'')}"></div>
  </div>
  <div class=grid2 style="margin-top:12px">
    <div><label>Mode</label><select id=mode><option ${d.mode==='draft_only'?'selected':''}>draft_only</option><option ${d.mode==='approved_only'?'selected':''}>approved_only</option><option ${d.mode==='auto'?'selected':''}>auto</option></select></div>
    <div><label>Status</label><input id=status_field value="${esc(d.status)}"></div>
  </div>
  <div style="margin-top:12px"><label>Body</label><textarea id=body>${esc(d.body)}</textarea></div>
  <div style="margin-top:12px"><label>Tags (comma separated)</label><input id=tags value="${esc((d.tags||[]).join(', '))}"></div>
  <div style="margin-top:12px"><label>Recommended people (comma separated)</label><input id=people value="${esc((d.recommended_people||[]).join(', '))}"></div>
  <div class=row style="margin-top:14px">
    <button onclick="saveItem()">Save</button>
    <button class=good onclick="setApproved(true)">Approve</button>
    <button class=warn onclick="setApproved(false)">Unapprove</button>
    <button class=secondary onclick="resetDraft()">Reset to drafted</button>
    <button class=bad onclick="publishNow()">Publish now</button>
  </div>
  <h3>Operator notes</h3>
  <pre>${esc((d.operator_notes||[]).join('\n'))}</pre>
  <h3>Raw payload</h3>
  <pre>${esc(JSON.stringify(d,null,2))}</pre>`;
}
function collectForm(){ return {title:document.getElementById('title').value,destination:document.getElementById('destination').value,mode:document.getElementById('mode').value,status:document.getElementById('status_field').value,body:document.getElementById('body').value,tags:document.getElementById('tags').value.split(',').map(x=>x.trim()).filter(Boolean),recommended_people:document.getElementById('people').value.split(',').map(x=>x.trim()).filter(Boolean)}; }
async function saveItem(){ const payload=collectForm(); const r=await fetch('/api/item?id='+encodeURIComponent(current),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}); currentData=await r.json(); await loadQueue(); }
async function setApproved(value){ const r=await fetch('/api/approve?id='+encodeURIComponent(current),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({approved:value})}); currentData=await r.json(); await loadQueue(); }
async function resetDraft(){ const r=await fetch('/api/item?id='+encodeURIComponent(current),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'drafted'})}); currentData=await r.json(); await loadQueue(); }
async function publishNow(){ const r=await fetch('/api/publish?id='+encodeURIComponent(current),{method:'POST'}); currentData=await r.json(); await loadQueue(); alert('Publish result: '+(currentData.publish_result?.status||currentData.status)); }
loadQueue();
</script>
</body>
</html>'''


class QueueUI:
    def __init__(self, publish_dir: str | Path, publisher=None) -> None:
        self.publish_dir = Path(publish_dir)
        self.publisher = publisher
        self.publish_dir.mkdir(parents=True, exist_ok=True)

    def list_items(self) -> list[dict[str, Any]]:
        items = []
        for path in sorted(self.publish_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                items.append({
                    "id": payload.get("id"),
                    "repo": payload.get("repo"),
                    "outlet": payload.get("outlet"),
                    "destination": payload.get("destination"),
                    "status": payload.get("status"),
                    "approved": payload.get("approved", False),
                })
            except Exception:
                continue
        return items

    def get_path(self, item_id: str) -> Path:
        path = self.publish_dir / f"{item_id}.json"
        if not path.exists():
            raise FileNotFoundError(item_id)
        return path

    def load_item(self, item_id: str) -> dict[str, Any]:
        return json.loads(self.get_path(item_id).read_text(encoding="utf-8"))

    def save_item(self, item_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        payload = self.load_item(item_id)
        for key in ["title", "destination", "mode", "status", "body", "tags", "recommended_people"]:
            if key in patch:
                payload[key] = patch[key]
        self.get_path(item_id).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    def set_approved(self, item_id: str, approved: bool) -> dict[str, Any]:
        payload = self.load_item(item_id)
        payload["approved"] = approved
        self.get_path(item_id).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    def publish_item(self, item_id: str) -> dict[str, Any]:
        path = self.get_path(item_id)
        if not self.publisher:
            payload = self.load_item(item_id)
            payload["status"] = "ready_to_publish"
            self.get_path(item_id).write_text(json.dumps(payload, indent=2), encoding="utf-8")
            return payload
        self.publisher.publish_payload_file(path)
        return self.load_item(item_id)


def serve_queue_ui(publish_dir: str | Path, publisher=None, host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None:
    ui = QueueUI(publish_dir, publisher=publisher)

    class Handler(BaseHTTPRequestHandler):
        def _json(self, payload: Any, status: int = 200) -> None:
            data = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                return json.loads(raw.decode("utf-8"))
            except Exception:
                return {}

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                data = HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            if parsed.path == "/api/queue":
                return self._json(ui.list_items())
            if parsed.path == "/api/item":
                item_id = parse_qs(parsed.query).get("id", [""])[0]
                try:
                    return self._json(ui.load_item(item_id))
                except FileNotFoundError:
                    return self._json({"error": "not found"}, status=404)
            return self._json({"error": "not found"}, status=404)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            item_id = parse_qs(parsed.query).get("id", [""])[0]
            body = self._body()
            try:
                if parsed.path == "/api/item":
                    return self._json(ui.save_item(item_id, body))
                if parsed.path == "/api/approve":
                    return self._json(ui.set_approved(item_id, bool(body.get("approved", False))))
                if parsed.path == "/api/publish":
                    return self._json(ui.publish_item(item_id))
            except FileNotFoundError:
                return self._json({"error": "not found"}, status=404)
            except Exception as exc:
                return self._json({"error": str(exc)}, status=500)
            return self._json({"error": "not found"}, status=404)

        def log_message(self, fmt: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}/"
    print(f"[queue-ui] serving {url}")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
