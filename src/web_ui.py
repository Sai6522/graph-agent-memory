"""
Graph-Native Agent Memory — Hackathon-quality web UI.

Rebuilt for the Relate by Neo4j Hackathon:
- Professional dark UI matching Relate's design language
- Interactive vis-network graph (draggable, animated, physics)
- Live Cypher queries shown as badges — judges see the actual Relate queries
- Real-time: any query instantly updates both results and graph
- Entity badges, contradiction highlighting, session timeline
- Store new memories and watch the graph grow live
"""
import sys
import os
import json
import time
import threading
from flask import Response

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template_string, request, jsonify
from src.memory_store import AgentMemory

STORE_PATH = os.environ.get("MEMORY_STORE", "./memory.rl")
app = Flask(__name__)
_mem = None
_agent = None
_db_lock = threading.Lock()
_agent_lock = threading.Lock()


def get_memory():
    global _mem
    if _mem is None:
        _mem = AgentMemory(STORE_PATH)
    return _mem


def get_agent():
    global _agent
    if _agent is None:
        # Share the same memory instance — avoids double-locking the store
        mem = get_memory()
        from src.agent import MemoryAgent
        _agent = MemoryAgent.__new__(MemoryAgent)
        _agent.memory = mem
        from groq import Groq
        import os, time as _time
        _agent.client = Groq(api_key=os.environ.get("GROQ_API_KEY", "YOUR_GROQ_API_KEY_HERE"))
        _agent.session_id = f"agent-{int(_time.time())}"
        _agent.tool_log = []
        mem.create_session(_agent.session_id, "AI Agent Chat", _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()))
    return _agent


@app.route("/api/query_graph", methods=["POST"])
def api_query_graph():
    data = request.json
    query = data.get("query", "")
    limit = data.get("limit", 6)
    with _db_lock:
        mem = get_memory()
        episodes = mem.recall_semantic(query, limit=limit)
        episode_ids = [e["id"] for e in episodes if "id" in e]
        nodes, edges, seen = [], [], set()
        ep_scores = {e["id"]: e.get("score", 0) for e in episodes}
        for ep in episodes:
            eid = ep["id"]
            if eid not in seen:
                seen.add(eid)
                score = ep.get("score", 0)
                is_decision = ep.get("type") == "decision"
                nodes.append({
                    "id": eid, "label": ep.get("content","")[:45] + ("…" if len(ep.get("content","")) > 45 else ""),
                    "group": "episode", "size": 18 + int(score * 20),
                    "color": {"background": "#f778ba" if is_decision else "#8b949e", "border": "#30363d", "highlight": {"background": "#f778ba", "border": "#58a6ff"}},
                    "shape": "dot", "font": {"size": 10, "color": "#e6edf3"},
                    "title": f"<b>Episode</b>: {ep.get('content','')}<br>Type: {ep.get('type','?')} | Score: {score:.3f}<br>Time: {ep.get('timestamp','?')[:16]}"
                })
        if episode_ids:
            for row in mem.db.execute(
                "MATCH (e:Episode)-[:MENTIONS]->(ent:Entity) WHERE e.id IN $ids "
                "RETURN e.id AS eid, ent.name AS ename, ent.entity_type AS etype, ent.description AS desc",
                {"ids": episode_ids}
            ):
                ename, eid, etype = row["ename"], row["eid"], row.get("etype","Entity")
                type_color = {"Person":"#2ea043","Technology":"#58a6ff","Concept":"#d29922","Project":"#f778ba"}.get(etype,"#8b949e")
                if ename not in seen:
                    seen.add(ename)
                    nodes.append({
                        "id": ename, "label": ename, "group": "entity", "size": 28,
                        "color": {"background": type_color, "border": "#161b22", "highlight": {"background": type_color, "border": "#fff"}},
                        "shape": "box", "font": {"size": 12, "color": "#fff", "bold": True},
                        "title": f"<b>{ename}</b><br>Type: {etype}<br>{row.get('desc','')}"
                    })
                ek = f"{eid}→{ename}"
                if ek not in seen:
                    seen.add(ek)
                    edges.append({"from": eid, "to": ename, "label": "MENTIONS",
                        "color": {"color": "#30363d55", "highlight": "#58a6ff"}, "arrows": "to",
                        "font": {"size": 8, "color": "#8b949e55"}, "width": 1})
            entity_names = [n["id"] for n in nodes if n["group"] == "entity"]
            if entity_names:
                for row in mem.db.execute(
                    "MATCH (a:Entity)-[r]->(b:Entity) WHERE a.name IN $n AND b.name IN $n "
                    "RETURN a.name AS src, b.name AS tgt, type(r) AS rel",
                    {"n": entity_names}
                ):
                    ek = f"{row['src']}-{row['rel']}-{row['tgt']}"
                    if ek not in seen:
                        seen.add(ek)
                        edges.append({"from": row["src"], "to": row["tgt"], "label": row["rel"],
                            "color": {"color": "#1f6feb", "highlight": "#58a6ff"}, "arrows": "to",
                            "font": {"size": 9, "color": "#58a6ff"}, "width": 2})
            if len(episode_ids) > 1:
                for row in mem.db.execute(
                    "MATCH (e1:Episode)-[:CONTRADICTS]->(e2:Episode) WHERE e1.id IN $ids AND e2.id IN $ids "
                    "RETURN e1.id AS src, e2.id AS tgt",
                    {"ids": episode_ids}
                ):
                    ek = f"{row['src']}-CONTRADICTS-{row['tgt']}"
                    if ek not in seen:
                        seen.add(ek)
                        edges.append({"from": row["src"], "to": row["tgt"], "label": "⚠ CONTRADICTS",
                            "color": {"color": "#f85149", "highlight": "#f85149"}, "arrows": "to",
                            "font": {"size": 10, "color": "#f85149"}, "width": 3, "dashes": True})
    return jsonify({"nodes": nodes, "edges": edges, "query": query, "count": len(episodes)})


@app.route("/api/entity_graph", methods=["POST"])
def api_entity_graph():
    data = request.json
    entity_name = data.get("entity_name", "")
    with _db_lock:
        mem = get_memory()
        nodes, edges, seen = [], [], set()
        # Center entity
        for row in mem.db.execute("MATCH (e:Entity {name:$n}) RETURN e.name AS name, e.entity_type AS etype, e.description AS desc", {"n": entity_name}):
            tc = {"Person":"#2ea043","Technology":"#58a6ff","Concept":"#d29922","Project":"#f778ba"}.get(row.get("etype",""),"#8b949e")
            seen.add(entity_name)
            nodes.append({"id":entity_name,"label":entity_name,"group":"entity_center","size":35,
                "color":{"background":tc,"border":"#fff"},"shape":"star","font":{"size":14,"color":"#fff","bold":True},
                "title":f"<b>{entity_name}</b><br>Type:{row.get('etype','')}<br>{row.get('desc','')}"})
        # Neighbors + episodes
        for row in mem.db.execute(
            "MATCH (e:Entity {name:$n})-[r]-(b:Entity) RETURN b.name AS bname, b.entity_type AS btype, type(r) AS rel, startNode(r).name AS src",
            {"n": entity_name}
        ):
            bname = row["bname"]
            tc = {"Person":"#2ea043","Technology":"#58a6ff","Concept":"#d29922","Project":"#f778ba"}.get(row.get("btype",""),"#8b949e")
            if bname not in seen:
                seen.add(bname)
                nodes.append({"id":bname,"label":bname,"group":"entity","size":25,
                    "color":{"background":tc,"border":"#161b22"},"shape":"box","font":{"size":11,"color":"#fff"},
                    "title":f"<b>{bname}</b>"})
            ek = f"{row['src']}-{row['rel']}-{bname}"
            if ek not in seen:
                seen.add(ek)
                edges.append({"from":row["src"],"to":bname,"label":row["rel"],
                    "color":{"color":"#1f6feb"},"arrows":"to","font":{"size":9,"color":"#58a6ff"},"width":2})
        # Episodes that mention this entity
        for row in mem.db.execute(
            "MATCH (ep:Episode)-[:MENTIONS]->(e:Entity {name:$n}) RETURN ep.id AS id, ep.content AS content, ep.episode_type AS etype, ep.timestamp AS ts LIMIT 8",
            {"n": entity_name}
        ):
            eid = row["id"]
            if eid and eid not in seen:
                seen.add(eid)
                nodes.append({"id":eid,"label":row.get("content","")[:40]+"…","group":"episode","size":16,
                    "color":{"background":"#f778ba" if row.get("etype")=="decision" else "#8b949e","border":"#30363d"},
                    "shape":"dot","font":{"size":9,"color":"#e6edf3"},
                    "title":f"{row.get('content','')}<br>{row.get('ts','?')[:16]}"})
                edges.append({"from":eid,"to":entity_name,"label":"MENTIONS",
                    "color":{"color":"#30363d55"},"arrows":"to","font":{"size":8,"color":"#8b949e44"},"width":1})
    return jsonify({"nodes":nodes,"edges":edges})


@app.route("/api/stats")
def api_stats():
    with _db_lock:
        return jsonify(get_memory().get_stats())


@app.route("/api/graph")
def api_graph():
    with _db_lock:
        return jsonify(get_memory().get_full_graph())

@app.route("/api/entities")
def api_entities():
    with _db_lock:
        mem = get_memory()
        r = mem.db.execute("MATCH (e:Entity) RETURN e.name AS name, e.entity_type AS type, e.description AS desc")
        return jsonify([dict(row) for row in r])

@app.route("/api/recall/semantic", methods=["POST"])
def api_recall_semantic():
    d = request.json
    with _db_lock:
        return jsonify(get_memory().recall_semantic(d["query"], d.get("limit",6)))

@app.route("/api/relational", methods=["POST"])
def api_relational():
    d = request.json
    with _db_lock:
        return jsonify(get_memory().recall_relational(d["entity_name"], d.get("hops",2)))

@app.route("/api/temporal", methods=["POST"])
def api_temporal():
    d = request.json
    with _db_lock:
        return jsonify(get_memory().recall_temporal(d["entity_name"], d.get("before"), d.get("after")))

@app.route("/api/contradictions")
def api_contradictions():
    with _db_lock:
        return jsonify(get_memory().detect_contradictions())

@app.route("/api/store", methods=["POST"])
def api_store():
    d = request.json
    eid = f"e{int(time.time()*1000)}"
    with _db_lock:
        mem = get_memory()
        mem.store_episode(eid,"web-ui",d["content"],
            time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
            episode_type=d.get("episode_type","message"),mentions=d.get("mentions"))
        # Auto-detect contradictions after storing
        contradictions = mem.detect_contradictions()
        explicit = [c for c in contradictions if c.get("contradiction_type") == "explicit"]
    return jsonify({"episode_id":eid,"status":"stored",
                    "new_contradictions": len(explicit)})


@app.route("/api/hybrid", methods=["POST"])
def api_hybrid():
    """Hybrid search: VECTOR INDEX + FULLTEXT INDEX merged via Reciprocal Rank Fusion."""
    d = request.json
    with _db_lock:
        return jsonify(get_memory().recall_hybrid(
            d["query"], d.get("keywords"), d.get("limit", 6)
        ))


@app.route("/api/cypher", methods=["POST"])
def api_cypher():
    """Live Cypher playground — run any read-only Cypher query."""
    d = request.json
    query = d.get("query", "").strip()
    if not query:
        return jsonify({"error": "No query provided"}), 400
    # Safety: block write operations from the playground
    blocked = ["CREATE ", "MERGE ", "SET ", "DELETE ", "REMOVE ", "DROP "]
    if any(b in query.upper() for b in blocked):
        return jsonify({"error": "Playground is read-only. Use the Store tab to write data."}), 400
    with _db_lock:
        try:
            rows = get_memory().run_cypher(query)
            return jsonify({"rows": rows, "count": len(rows)})
        except Exception as e:
            return jsonify({"error": str(e)}), 400


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """SSE endpoint: runs the Groq agent with Relate memory tools, streams events."""
    data = request.json
    user_message = data.get("message", "")
    history = data.get("history", [])

    def generate():
        with _db_lock:
            agent = get_agent()
            for event in agent.chat(user_message, history):
                yield f"data: {json.dumps(event)}\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/")
def index():
    return render_template_string(HTML)


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Graph-Native Agent Memory — Relate Hackathon</title>
<script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0d1117;color:#e6edf3}
#topbar{height:52px;background:#161b22;border-bottom:1px solid #30363d;display:flex;align-items:center;justify-content:space-between;padding:0 20px;flex-shrink:0}
.logo{display:flex;align-items:center;gap:10px}
.logo-title{font-size:15px;font-weight:600}.logo-title span{color:#58a6ff}
.live-pill{background:#21262d;border:1px solid #30363d;border-radius:20px;padding:3px 12px;font-size:11px;color:#8b949e;display:flex;align-items:center;gap:6px}
.live-dot{width:6px;height:6px;border-radius:50%;background:#2ea043;box-shadow:0 0 6px #2ea043;animation:blink 2s infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.4}}
.stats{display:flex;gap:20px}.stat{font-size:12px;color:#8b949e}.stat b{color:#e6edf3;font-weight:600}
#layout{display:flex;height:calc(100vh - 52px)}
#sidebar{width:380px;min-width:380px;border-right:1px solid #30363d;display:flex;flex-direction:column;overflow:hidden}
#graph-area{flex:1;min-width:0;display:flex;flex-direction:column}
.tabs{display:flex;flex-shrink:0;border-bottom:1px solid #30363d;background:#161b22;height:40px}
.tab{flex:1;height:40px;cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:500;color:#8b949e;border-bottom:2px solid transparent;transition:all .15s}
.tab:hover{color:#e6edf3;background:#21262d}.tab.active{color:#58a6ff;border-bottom-color:#58a6ff;background:#0d1117}
.panel{display:none;flex:1;min-height:0;flex-direction:column;overflow-y:auto;padding:14px;gap:12px}
.panel.active{display:flex}
#tab-chat{padding:0;overflow:hidden}
#chat-msgs{flex:1;min-height:0;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:8px}
#tool-log{flex-shrink:0;max-height:95px;overflow-y:auto;border-top:1px solid #30363d;padding:6px 12px;display:none;flex-direction:column;gap:3px;background:#0d1117}
#chat-bar{flex-shrink:0;display:flex;gap:8px;padding:10px 12px;border-top:1px solid #30363d;background:#161b22}
#graph-topbar{flex-shrink:0;height:44px;background:#161b22;border-bottom:1px solid #30363d;display:flex;align-items:center;justify-content:space-between;padding:0 16px}
#graph-net{flex:1;min-height:0;width:100%;background:#0d1117;display:block}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:14px}
.card h3{font-size:12px;font-weight:600;color:#58a6ff;margin-bottom:10px}
input,select,textarea{width:100%;background:#0d1117;border:1px solid #30363d;color:#e6edf3;padding:7px 11px;border-radius:6px;font-size:13px;outline:none;font-family:inherit;transition:border-color .2s}
input:focus,textarea:focus,select:focus{border-color:#58a6ff}
textarea{resize:vertical;min-height:52px}
.lbl{font-size:11px;color:#8b949e;display:block;margin-bottom:4px}
.field{display:flex;flex-direction:column;gap:4px}
.btn{border:none;padding:7px 16px;border-radius:6px;font-size:12px;font-weight:500;cursor:pointer;font-family:inherit;transition:all .15s}
.btn-primary{background:#238636;color:#fff}.btn-primary:hover{background:#2ea043}
.btn-sec{background:#21262d;color:#e6edf3;border:1px solid #30363d}.btn-sec:hover{background:#30363d;border-color:#58a6ff;color:#58a6ff}
.btn-sm{padding:4px 10px;font-size:11px}
.btn-row{display:flex;gap:6px;margin-top:8px;flex-wrap:wrap}
.mrow{display:flex;gap:6px;margin-top:8px}
.mbtn{flex:1;padding:6px;border-radius:6px;font-size:11px;font-weight:600;cursor:pointer;border:1px solid #30363d;background:#0d1117;color:#8b949e;text-align:center;transition:all .15s}
.mbtn.active{background:#1f6feb22;border-color:#58a6ff;color:#58a6ff}
.mbtn:hover:not(.active){border-color:#8b949e;color:#e6edf3}
.ri{background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:9px 11px;margin-bottom:5px;cursor:pointer;transition:border-color .15s}
.ri:hover{border-color:#58a6ff}
.rm{font-size:10px;color:#8b949e;margin-bottom:3px;display:flex;gap:6px;flex-wrap:wrap}
.rt{font-size:12px;line-height:1.5}
.sc{color:#58a6ff;font-weight:700}
.tb{padding:1px 6px;border-radius:4px;font-size:10px;font-weight:600}
.td{background:#f778ba22;color:#f778ba}.tm{background:#58a6ff22;color:#58a6ff}
.to{background:#2ea04322;color:#2ea043}.tq{background:#d2992222;color:#d29922}
.eb{display:inline-flex;align-items:center;padding:3px 9px;margin:2px;border-radius:5px;font-size:11px;cursor:pointer;border:1px solid transparent;transition:all .15s}
.eb:hover{transform:scale(1.08);border-color:currentColor}
.ePerson{background:#2ea04322;color:#2ea043}.eTechnology{background:#58a6ff22;color:#58a6ff}
.eConcept{background:#d2992222;color:#d29922}.eProject{background:#f778ba22;color:#f778ba}
.con{border:1px solid #f8514944;background:#f8514908;border-radius:6px;padding:10px;margin-bottom:6px}
.con-lbl{color:#f85149;font-size:11px;font-weight:700;margin-bottom:4px}
.con-txt{font-size:11px;color:#8b949e;margin-top:3px}.con-txt b{color:#e6edf3}
.msg{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px 13px}
.msg-lbl{font-size:10px;font-weight:700;margin-bottom:5px}
.msg-body{font-size:13px;line-height:1.6}
.msg-body b{font-weight:600}
.msg-body code{background:#21262d;padding:1px 5px;border-radius:3px;font-size:11px}
.trow{display:flex;gap:6px;align-items:center;font-size:10px}
.tn{background:#1f6feb22;color:#58a6ff;padding:2px 7px;border-radius:4px;font-weight:700;white-space:nowrap}
.tc{color:#8b949e;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.tk{color:#2ea043;white-space:nowrap}
.cyb{background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:8px 10px;font-family:'SF Mono',Consolas,monospace;font-size:11px;color:#79c0ff;overflow-x:auto;white-space:pre;margin-top:8px;line-height:1.5;display:none}
.kw{color:#ff7b72}
.leg{display:flex;align-items:center;gap:5px;font-size:11px;color:#8b949e}
.ld{width:10px;height:10px;border-radius:50%}
.lb{width:12px;height:8px;border-radius:2px}
#toast{position:fixed;bottom:20px;right:20px;z-index:9999;background:#238636;color:#fff;padding:10px 20px;border-radius:8px;font-size:13px;transform:translateY(80px);transition:transform .3s cubic-bezier(.34,1.56,.64,1)}
#toast.show{transform:translateY(0)}
.empty{color:#8b949e;font-size:12px;padding:10px;font-style:italic;text-align:center}
::-webkit-scrollbar{width:4px;height:4px}
::-webkit-scrollbar-track{background:#0d1117}
::-webkit-scrollbar-thumb{background:#30363d;border-radius:4px}
</style>
</head>
<body>

<div id="topbar">
  <div class="logo">
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
      <circle cx="11" cy="11" r="4" fill="#58a6ff"/>
      <circle cx="4" cy="4" r="2.5" fill="#2ea043"/>
      <circle cx="18" cy="4" r="2.5" fill="#f778ba"/>
      <circle cx="4" cy="18" r="2.5" fill="#d29922"/>
      <circle cx="18" cy="18" r="2.5" fill="#8b949e"/>
      <line x1="11" y1="7" x2="4" y2="4" stroke="#58a6ff44" stroke-width="1.2"/>
      <line x1="11" y1="7" x2="18" y2="4" stroke="#58a6ff44" stroke-width="1.2"/>
      <line x1="11" y1="15" x2="4" y2="18" stroke="#58a6ff44" stroke-width="1.2"/>
      <line x1="11" y1="15" x2="18" y2="18" stroke="#58a6ff44" stroke-width="1.2"/>
    </svg>
    <div class="logo-title">Graph-Native <span>Agent Memory</span></div>
    <div class="live-pill"><span class="live-dot"></span>Relate v1.0.1 · Live</div>
  </div>
  <div class="stats">
    <div class="stat"><b id="s-ep">–</b> episodes</div>
    <div class="stat"><b id="s-ent">–</b> entities</div>
    <div class="stat"><b id="s-rel">–</b> relationships</div>
    <div class="stat"><b id="s-con">–</b> contradictions</div>
  </div>
</div>

<div id="layout">
  <div id="sidebar">
    <div class="tabs">
      <div class="tab active" onclick="switchTab('chat')">🤖 AI Chat</div>
      <div class="tab" onclick="switchTab('query')">🔍 Query</div>
      <div class="tab" onclick="switchTab('store')">📝 Store</div>
      <div class="tab" onclick="switchTab('explore')">🗂 Explore</div>
      <div class="tab" onclick="switchTab('cypher')">⌨️ Cypher</div>
    </div>

    <!-- CHAT -->
    <div class="panel active" id="tab-chat">
      <div id="chat-msgs">
        <div class="msg">
          <div class="msg-lbl" style="color:#58a6ff">🤖 Agent (Groq + Relate)</div>
          <div class="msg-body">Hello! I have access to your project graph memory.<br><br>
          Try:<br>• <i>"What authentication decisions were made?"</i><br>
          • <i>"What do you know about Alice?"</i><br>
          • <i>"Are there any contradictions?"</i><br>
          • <i>"Remember: we chose TypeScript for the frontend"</i></div>
        </div>
      </div>
      <div id="tool-log">
        <div style="font-size:10px;color:#8b949e;font-weight:600;margin-bottom:3px">RELATE TOOL CALLS</div>
      </div>
      <div id="chat-bar">
        <input type="text" id="chat-input" placeholder="Ask anything about your memories…"
          onkeydown="if(event.key==='Enter')sendChat()" style="flex:1">
        <button class="btn btn-primary" id="chat-btn" onclick="sendChat()">Send</button>
      </div>
    </div>

    <!-- QUERY -->
    <div class="panel" id="tab-query">
      <div class="card">
        <h3>🔍 Memory Query</h3>
        <div class="field">
          <input type="text" id="q-input" value="what database did we choose?"
            placeholder="e.g. what database did we choose?"
            onkeydown="if(event.key==='Enter')runQuery(curMode)">
        </div>
        <div class="mrow">
          <div class="mbtn active" id="m-semantic"   onclick="setMode('semantic')">🔍 Semantic</div>
          <div class="mbtn"        id="m-relational" onclick="setMode('relational')">🔗 Relational</div>
          <div class="mbtn"        id="m-temporal"   onclick="setMode('temporal')">⏰ Temporal</div>
          <div class="mbtn"        id="m-hybrid"     onclick="setMode('hybrid')">⚡ Hybrid</div>
        </div>
        <div class="field" id="ent-row" style="display:none;margin-top:8px">
          <label class="lbl">Entity</label>
          <select id="ent-sel" onchange="if(this.value){document.getElementById('q-input').value=this.value;runQuery(curMode)}">
            <option value="">— pick entity —</option>
          </select>
        </div>
        <div class="btn-row">
          <button class="btn btn-primary" onclick="runQuery(curMode)" style="flex:1">Run → Graph</button>
          <button class="btn btn-sec" onclick="showFullGraph()">Full Graph</button>
        </div>
        <pre class="cyb" id="cypher-box"></pre>
      </div>
      <div class="card" style="flex:1;min-height:120px;overflow:hidden;display:flex;flex-direction:column">
        <h3>📋 Results <span id="r-count" style="color:#8b949e;font-weight:400"></span></h3>
        <div id="results" style="flex:1;overflow-y:auto"><div class="empty">Run a query</div></div>
      </div>
    </div>

    <!-- STORE -->
    <div class="panel" id="tab-store">
      <div class="card">
        <h3>📝 Store Memory</h3>
        <div class="field">
          <label class="lbl">What happened?</label>
          <textarea id="new-content" placeholder="Alice decided to use PostgreSQL…"></textarea>
        </div>
        <div class="field" style="margin-top:8px">
          <label class="lbl">Type</label>
          <select id="new-type">
            <option value="decision">Decision</option>
            <option value="message">Message</option>
            <option value="observation">Observation</option>
            <option value="question">Question</option>
          </select>
        </div>
        <div class="field" style="margin-top:8px">
          <label class="lbl">Mentioned entities (comma-separated)</label>
          <input type="text" id="new-mentions" placeholder="Alice Chen, PostgreSQL">
        </div>
        <div class="btn-row">
          <button class="btn btn-primary" onclick="storeEpisode()" style="flex:1">💾 Store & Refresh</button>
        </div>
      </div>
      <div class="card">
        <h3>⚠️ Contradictions</h3>
        <div id="contradictions"><div class="empty">Loading…</div></div>
      </div>
    </div>

    <!-- EXPLORE -->
    <div class="panel" id="tab-explore">
      <div class="card">
        <h3>🏷️ Entities <span style="font-size:10px;color:#8b949e">(click to explore)</span></h3>
        <div id="entities"><div class="empty">Loading…</div></div>
      </div>
      <div class="card">
        <h3>ℹ️ Store Info</h3>
        <div id="schema-info" style="font-size:12px;color:#8b949e;line-height:1.9"></div>
      </div>
    </div>

    <!-- CYPHER PLAYGROUND -->
    <div class="panel" id="tab-cypher">
      <div class="card">
        <h3>⌨️ Live Cypher Playground</h3>
        <div style="font-size:11px;color:#8b949e;margin-bottom:8px">Run any read-only Cypher query directly against <b style="color:#58a6ff">memory.rl</b></div>
        <textarea id="cy-input" style="font-family:'SF Mono',Consolas,monospace;font-size:12px;min-height:100px;color:#79c0ff;background:#0d1117" placeholder="MATCH (e:Episode)-[:MENTIONS]->(ent:Entity)&#10;RETURN e.content, ent.name&#10;ORDER BY e.timestamp DESC LIMIT 10"></textarea>
        <div class="btn-row">
          <button class="btn btn-primary" onclick="runCypher()" style="flex:1">▶ Run Query</button>
          <button class="btn btn-sec" onclick="setCyEx(0)">Episodes</button>
          <button class="btn btn-sec" onclick="setCyEx(1)">Entities</button>
          <button class="btn btn-sec" onclick="setCyEx(2)">Contradictions</button>
        </div>
      </div>
      <div class="card" style="flex:1;min-height:0;overflow:hidden;display:flex;flex-direction:column">
        <h3>📊 Results <span id="cy-count" style="color:#8b949e;font-weight:400"></span></h3>
        <div id="cy-results" style="flex:1;overflow-y:auto;font-size:12px"><div class="empty">Run a query above</div></div>
      </div>
    </div>

  </div>

  <!-- GRAPH -->
  <div id="graph-area">
    <div id="graph-topbar">
      <div style="font-size:12px;color:#8b949e">
        <b id="graph-label" style="color:#e6edf3">Full memory graph</b>
        <span id="graph-sub" style="margin-left:8px"></span>
      </div>
      <div style="display:flex;gap:12px;align-items:center">
        <div class="leg"><div class="lb" style="background:#f778ba"></div> Decision</div>
        <div class="leg"><div class="ld" style="background:#8b949e"></div> Episode</div>
        <div class="leg"><div class="lb" style="background:#58a6ff"></div> Technology</div>
        <div class="leg"><div class="lb" style="background:#2ea043"></div> Person</div>
        <button class="btn btn-sec btn-sm" onclick="showFullGraph()">🌐 Full</button>
      </div>
    </div>
    <div id="graph-net"></div>
  </div>
</div>

<div id="toast"></div>

<script>
const PHYSICS={barnesHut:{gravitationalConstant:-6000,centralGravity:.3,springLength:120,springConstant:.04,damping:.45,avoidOverlap:.3},stabilization:{iterations:120,updateInterval:25,fit:true}};
const VOPTS={physics:PHYSICS,nodes:{borderWidth:2,shadow:{enabled:true,color:'rgba(0,0,0,.4)',size:10,x:3,y:3}},edges:{smooth:{type:'continuous',roundness:.3},arrows:{to:{scaleFactor:.6}}},interaction:{hover:true,tooltipDelay:100,zoomView:true,dragView:true,dragNodes:true,multiselect:false,keyboard:false}};
let network=null,ALL_ENTITIES=[],curMode='semantic',chatHistory=[],chatBusy=false;

// Graph
function drawGraph(nodes,edges,label,sub){
  const el=document.getElementById('graph-net');
  const data={nodes:new vis.DataSet(nodes),edges:new vis.DataSet(edges)};
  if(network){network.destroy();network=null}
  network=new vis.Network(el,data,VOPTS);
  document.getElementById('graph-label').textContent=label||'Graph';
  document.getElementById('graph-sub').textContent=sub||'';
  network.on('stabilizationIterationsDone',()=>{
    document.getElementById('graph-sub').textContent=`${nodes.length} nodes · ${edges.length} edges`;
  });
  network.on('click',p=>{
    if(p.nodes.length>0){const n=nodes.find(x=>x.id===p.nodes[0]);if(n&&n.group==='entity')loadEntityGraph(n.id);}
  });
}

function showFullGraph(){
  fetch('/api/graph').then(r=>r.json()).then(d=>{
    const TC={Person:'#2ea043',Technology:'#58a6ff',Concept:'#d29922',Project:'#f778ba'};
    const vn=d.nodes.map(n=>({id:n.id,label:(n.label||n.id).substring(0,18),group:n.group||'other',
      shape:n.group==='entity'?'box':'dot',size:n.group==='entity'?24:14,
      color:{background:TC[n.type]||(n.group==='entity'?'#58a6ff':'#8b949e'),border:'#161b22'},
      font:{size:n.group==='entity'?11:9,color:'#e6edf3'},title:n.label||n.id}));
    const ve=d.edges.map(e=>({from:e.source,to:e.target,label:e.label||'',
      color:{color:'#30363d'},arrows:'to',font:{size:8,color:'#8b949e44'},width:1}));
    drawGraph(vn,ve,'Full memory graph','');
  });
}

function loadEntityGraph(name){
  fetch('/api/entity_graph',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({entity_name:name})
  }).then(r=>r.json()).then(d=>drawGraph(d.nodes,d.edges,`Entity: ${name}`,''));
}

// Stats
function loadStats(){
  fetch('/api/stats').then(r=>r.json()).then(d=>{
    document.getElementById('s-ep').textContent=d.Episode||0;
    document.getElementById('s-ent').textContent=d.Entity||0;
    document.getElementById('s-rel').textContent=d.relationships||0;
  });
  fetch('/api/contradictions').then(r=>r.json()).then(d=>{
    const ex=d.filter(c=>c.contradiction_type==='explicit');
    document.getElementById('s-con').textContent=ex.length;
    renderContradictions(d);
  });
}

// Entities
function loadEntities(){
  fetch('/api/entities').then(r=>r.json()).then(d=>{
    ALL_ENTITIES=d;
    document.getElementById('entities').innerHTML=
      d.map(e=>`<span class="eb e${e.type}" onclick="entityClick('${e.name}')">${e.name}</span>`).join('');
    const sel=document.getElementById('ent-sel');
    sel.innerHTML='<option value="">— pick entity —</option>'+
      d.map(e=>`<option value="${e.name}">${e.name} (${e.type})</option>`).join('');
    const types={};d.forEach(e=>{types[e.type]=(types[e.type]||0)+1});
    document.getElementById('schema-info').innerHTML=
      Object.entries(types).map(([t,c])=>`<div>🏷 ${t}: <b style="color:#e6edf3">${c}</b></div>`).join('')+
      '<div style="margin-top:8px">Node labels: Session, Episode, Entity, Attribute, Topic</div>'+
      '<div>Rel types: MENTIONS, CONTRADICTS, SUPPORTS, HAS_ATTRIBUTE…</div>'+
      '<div style="margin-top:8px">Vector indexes: episode_embedding, entity_embedding (384-dim cosine)</div>';
  });
}

function entityClick(name){
  document.getElementById('ent-sel').value=name;
  document.getElementById('q-input').value=name;
  setMode('relational');runQuery('relational');switchTab('query');
}

// Tabs
function switchTab(name){
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  const idx={chat:0,query:1,store:2,explore:3,cypher:4}[name];
  document.querySelectorAll('.tab')[idx].classList.add('active');
  document.getElementById('tab-'+name).classList.add('active');
}

// Mode
function setMode(m){
  curMode=m;
  ['semantic','relational','temporal','hybrid'].forEach(x=>{
    const el=document.getElementById('m-'+x);
    if(el) el.classList.toggle('active',x===m);
  });
  document.getElementById('ent-row').style.display=(m==='relational'||m==='temporal')?'flex':'none';
  updateCypher(m);
}
function updateCypher(m){
  const q=document.getElementById('q-input').value;
  const ent=document.getElementById('ent-sel').value||q;
  const kw=s=>`<span class="kw">${s}</span>`;
  const box=document.getElementById('cypher-box');
  if(m==='semantic')
    box.innerHTML=`${kw('MATCH')} (e:Episode)\n${kw('SEARCH')} e ${kw('IN')} (${kw('VECTOR INDEX')} episode_embedding\n  ${kw('FOR')} $embedding ${kw('LIMIT')} 5) ${kw('SCORE AS')} score\n${kw('RETURN')} e.id, e.content, score\n${kw('ORDER BY')} score ${kw('DESC')}`;
  else if(m==='relational')
    box.innerHTML=`${kw('MATCH')} (ent:Entity {name:"${ent}"})\n      -[*1..2]-(conn:Entity)\n      <-[:MENTIONS]-(e:Episode)\n${kw('RETURN DISTINCT')} e.content, conn.name\n${kw('ORDER BY')} e.timestamp ${kw('DESC LIMIT')} 20`;
  else if(m==='temporal')
    box.innerHTML=`${kw('MATCH')} (e:Episode)-[:MENTIONS]->\n      (Entity {name:"${ent}"})\n${kw('WHERE')} e.timestamp ${kw('IS NOT NULL')}\n${kw('RETURN')} e.content, e.timestamp\n${kw('ORDER BY')} e.timestamp ${kw('DESC')}`;
  else
    box.innerHTML=`${kw('// Hybrid: VECTOR INDEX + FULLTEXT INDEX → RRF merge')}\n${kw('MATCH')} (e:Episode)\n${kw('SEARCH')} e ${kw('IN')} (${kw('VECTOR INDEX')} episode_embedding ${kw('FOR')} $embedding ${kw('LIMIT')} 6) ${kw('SCORE AS')} v\n${kw('WITH')} e, v\n${kw('SEARCH')} e ${kw('IN')} (${kw('FULLTEXT INDEX')} episode_fulltext ${kw('FOR')} "${q}" ${kw('LIMIT')} 6) ${kw('SCORE AS')} ft\n${kw('RETURN')} e.content, v, ft, (v+ft)/2 ${kw('AS')} hybrid ${kw('ORDER BY')} hybrid ${kw('DESC')}`;
  box.style.display='block';
}

// Query
function findEnt(q){q=q.toLowerCase();for(const e of ALL_ENTITIES)if(q.includes(e.name.toLowerCase()))return e.name;return null}

function runQuery(m){
  const q=document.getElementById('q-input').value.trim();if(!q)return;
  updateCypher(m);
  fetch('/api/query_graph',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({query:q,limit:6})
  }).then(r=>r.json()).then(d=>drawGraph(d.nodes,d.edges,`"${q.substring(0,40)}"`,`${d.count} episodes found`));

  let ep='/api/recall/semantic',body={query:q,limit:6};
  if(m==='relational'||m==='temporal'){
    const ent=document.getElementById('ent-sel').value||findEnt(q);
    if(!ent){document.getElementById('results').innerHTML='<div class="empty">Pick an entity from the dropdown or click one in Explore tab.</div>';return}
    if(m==='relational'){ep='/api/relational';body={entity_name:ent,hops:2};loadEntityGraph(ent);}
    else{ep='/api/temporal';body={entity_name:ent};}
  } else if(m==='hybrid'){
    ep='/api/hybrid';body={query:q,keywords:q,limit:6};
  }
  fetch(ep,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
    .then(r=>r.json()).then(d=>renderResults(d));
}

// Cypher playground
const CY_EXAMPLES = [
  'MATCH (e:Episode)-[:MENTIONS]->(ent:Entity)\nRETURN e.content, ent.name, e.episode_type\nORDER BY e.timestamp DESC LIMIT 10',
  'MATCH (ent:Entity)\nRETURN ent.name, ent.entity_type, ent.description\nORDER BY ent.entity_type, ent.name',
  'MATCH (new:Episode)-[r:CONTRADICTS]->(old:Episode)\nRETURN new.content AS new_decision, old.content AS old_decision,\n       r.reason AS reason, new.timestamp AS when'
];
function setCyEx(i){document.getElementById('cy-input').value=CY_EXAMPLES[i]}

function runCypher(){
  const q=document.getElementById('cy-input').value.trim();
  if(!q){document.getElementById('cy-results').innerHTML='<div class="empty">Enter a Cypher query above.</div>';return}
  document.getElementById('cy-results').innerHTML='<div class="empty">Running…</div>';
  fetch('/api/cypher',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query:q})})
    .then(r=>r.json()).then(d=>{
      if(d.error){document.getElementById('cy-results').innerHTML=`<div class="empty" style="color:#f85149">${d.error}</div>`;return}
      document.getElementById('cy-count').textContent=`(${d.count} rows)`;
      if(!d.rows||!d.rows.length){document.getElementById('cy-results').innerHTML='<div class="empty">No rows returned.</div>';return}
      const cols=Object.keys(d.rows[0]);
      let html=`<table style="width:100%;border-collapse:collapse;font-size:11px">
        <tr>${cols.map(c=>`<th style="padding:5px 8px;text-align:left;color:#58a6ff;border-bottom:1px solid #30363d;white-space:nowrap">${c}</th>`).join('')}</tr>
        ${d.rows.map((r,i)=>`<tr style="background:${i%2?'#161b22':'#0d1117'}">
          ${cols.map(c=>`<td style="padding:5px 8px;border-bottom:1px solid #30363d22;vertical-align:top;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${String(r[c]||'').replace(/"/g,'')}">${String(r[c]||'').substring(0,60)}</td>`).join('')}
        </tr>`).join('')}
      </table>`;
      document.getElementById('cy-results').innerHTML=html;
    }).catch(e=>document.getElementById('cy-results').innerHTML=`<div class="empty" style="color:#f85149">${e}</div>`);
}

function renderResults(data){
  const el=document.getElementById('results');
  document.getElementById('r-count').textContent=data&&data.length?`(${data.length})`:'';
  if(!data||!data.length){el.innerHTML='<div class="empty">No results.</div>';return}
  const tcls={decision:'td',message:'tm',observation:'to',question:'tq'};
  el.innerHTML=data.map(r=>{
    const sc=r.score?`<span class="sc">${r.score.toFixed(3)}</span>`:'';
    const tb=r.type?`<span class="tb ${tcls[r.type]||'tm'}">${r.type}</span>`:'';
    const ts=r.timestamp?`<span>${r.timestamp.substring(0,16)}</span>`:'';
    const via=r.via_entity?`<span>via: ${r.via_entity}</span>`:'';
    const cf=r.confidence!==undefined?`<span>${(r.confidence*100).toFixed(0)}%</span>`:'';
    return `<div class="ri"><div class="rm">${[sc,tb,ts,via,cf].filter(Boolean).join('')}</div>
      <div class="rt">${r.content||r.id||JSON.stringify(r)}</div></div>`;
  }).join('');
}

// Contradictions
function renderContradictions(data){
  const el=document.getElementById('contradictions');
  const ex=data.filter(c=>c.contradiction_type==='explicit');
  if(!ex.length){el.innerHTML='<div class="empty">No explicit contradictions.</div>';return}
  el.innerHTML=ex.map(c=>`<div class="con">
    <div class="con-lbl">⚠ Contradiction</div>
    <div class="con-txt"><b>Before:</b> ${(c.old_content||'?').substring(0,65)}</div>
    <div class="con-txt"><b>After:</b>  ${(c.new_content||'?').substring(0,65)}</div>
    ${c.reason?`<div class="con-txt" style="margin-top:4px;opacity:.6">${c.reason}</div>`:''}
  </div>`).join('');
}

// Store
function storeEpisode(){
  const content=document.getElementById('new-content').value.trim();if(!content)return;
  const etype=document.getElementById('new-type').value;
  const ms=document.getElementById('new-mentions').value;
  const mentions=ms?ms.split(',').map(s=>s.trim()).filter(Boolean):[];
  fetch('/api/store',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({content,episode_type:etype,mentions})
  }).then(r=>r.json()).then(d=>{
    document.getElementById('new-content').value='';
    document.getElementById('new-mentions').value='';
    toast('✅ Stored: '+d.episode_id);
    loadStats();loadEntities();showFullGraph();
  });
}

// Chat
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
function md(t){return t.replace(/\*\*(.+?)\*\*/g,'<b>$1</b>').replace(/`([^`]+)`/g,'<code>$1</code>').replace(/^## (.+)$/gm,'<b style="display:block;margin-top:8px">$1</b>').replace(/^- (.+)$/gm,'<div style="padding-left:12px">• $1</div>').replace(/\n/g,'<br>')}

function appendMsg(role,html){
  const box=document.getElementById('chat-msgs');
  const d=document.createElement('div');d.className='msg';
  const color=role==='user'?'#2ea043':'#58a6ff';
  const lbl=role==='user'?'👤 You':'🤖 Agent (Groq + Relate)';
  d.innerHTML=`<div class="msg-lbl" style="color:${color}">${lbl}</div><div class="msg-body">${html}</div>`;
  box.appendChild(d);box.scrollTop=99999;
  return d.querySelector('.msg-body');
}

function appendToolRow(tool,cypher,count){
  const tl=document.getElementById('tool-log');tl.style.display='flex';
  const d=document.createElement('div');d.className='trow';
  d.innerHTML=`<span class="tn">${tool}</span><span class="tc" title="${esc(cypher)}">${esc(cypher.split('\n')[0])}</span><span class="tk">${count} rows</span>`;
  tl.appendChild(d);tl.scrollTop=99999;
}

async function sendChat(){
  if(chatBusy)return;
  const input=document.getElementById('chat-input');
  const msg=input.value.trim();if(!msg)return;
  chatBusy=true;input.value='';
  document.getElementById('chat-btn').textContent='…';
  document.getElementById('chat-btn').disabled=true;
  const tl=document.getElementById('tool-log');
  tl.innerHTML='<div style="font-size:10px;color:#8b949e;font-weight:600;margin-bottom:3px">RELATE TOOL CALLS</div>';
  tl.style.display='none';
  appendMsg('user',esc(msg));
  chatHistory.push({role:'user',content:msg});
  const ab=appendMsg('agent','<span style="color:#8b949e">Searching graph…</span>');
  const resp=await fetch('/api/chat',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({message:msg,history:chatHistory.slice(-10)})});
  const reader=resp.body.getReader();const dec=new TextDecoder();
  let buf='',answer='';
  while(true){
    const {value,done}=await reader.read();if(done)break;
    buf+=dec.decode(value,{stream:true});
    const lines=buf.split('\n');buf=lines.pop();
    for(const line of lines){
      if(!line.startsWith('data: '))continue;
      try{
        const ev=JSON.parse(line.slice(6));
        if(ev.type==='tool_start'){ab.innerHTML=`<span style="color:#8b949e">🔍 <b style="color:#58a6ff">${ev.tool}</b>…</span>`;}
        else if(ev.type==='tool_result'){
          const r=ev.result||{};
          const cnt=r.count!==undefined?r.count:(r.results||r.contradictions||[]).length;
          appendToolRow(ev.tool,ev.cypher||'',cnt);
          if(ev.tool==='recall_semantic'&&r.results&&r.results.length>0){
            fetch('/api/query_graph',{method:'POST',headers:{'Content-Type':'application/json'},
              body:JSON.stringify({query:r.results[0].content||'',limit:6})
            }).then(x=>x.json()).then(gd=>drawGraph(gd.nodes,gd.edges,'Agent memory search',`${gd.nodes.length} nodes`));
          }
        }
        else if(ev.type==='text_delta'){answer+=ev.content;ab.innerHTML=md(answer);document.getElementById('chat-msgs').scrollTop=99999;}
        else if(ev.type==='done'){chatHistory.push({role:'assistant',content:answer});loadStats();loadEntities();}
      }catch(e){}
    }
  }
  chatBusy=false;
  document.getElementById('chat-btn').textContent='Send';
  document.getElementById('chat-btn').disabled=false;
  input.focus();
}

// Toast
function toast(msg){const t=document.getElementById('toast');t.textContent=msg;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2500)}

// Init
loadStats();loadEntities();showFullGraph();setTimeout(()=>runQuery('semantic'),600);
</script>
</body>
</html>
"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    store = STORE_PATH
    if "--store" in sys.argv:
        idx = sys.argv.index("--store")
        if idx + 1 < len(sys.argv):
            store = sys.argv[idx + 1]
    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        if idx + 1 < len(sys.argv):
            port = int(sys.argv[idx + 1])

    STORE_PATH = store
    _mem = AgentMemory(STORE_PATH)
    print(f"\n  Graph-Native Agent Memory")
    print(f"  Web UI → http://0.0.0.0:{port}")
    print(f"  Store  → {store}\n")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=False)
