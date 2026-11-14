"""
Generate a professional hackathon presentation for Graph-Native Agent Memory.
Produces: graph_agent_memory_presentation.pptx
"""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt
import copy

# ── Color palette (matches Relate dark theme) ────────────────
BG_DARK    = RGBColor(0x0D, 0x11, 0x17)   # #0d1117
BG_CARD    = RGBColor(0x16, 0x1B, 0x22)   # #161b22
BORDER     = RGBColor(0x30, 0x36, 0x3D)   # #30363d
BLUE       = RGBColor(0x58, 0xA6, 0xFF)   # #58a6ff
GREEN      = RGBColor(0x2E, 0xA0, 0x43)   # #2ea043
PURPLE     = RGBColor(0xF7, 0x78, 0xBA)   # #f778ba
YELLOW     = RGBColor(0xD2, 0x99, 0x22)   # #d29922
RED        = RGBColor(0xF8, 0x51, 0x49)   # #f85149
WHITE      = RGBColor(0xE6, 0xED, 0xF3)   # #e6edf3
MUTED      = RGBColor(0x8B, 0x94, 0x9E)   # #8b949e

SLIDE_W = Inches(13.33)
SLIDE_H = Inches(7.5)


def new_prs():
    prs = Presentation()
    prs.slide_width  = SLIDE_W
    prs.slide_height = SLIDE_H
    return prs


def blank_slide(prs):
    layout = prs.slide_layouts[6]  # completely blank
    return prs.slides.add_slide(layout)


def bg(slide, color=BG_DARK):
    """Fill slide background."""
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def box(slide, left, top, width, height, fill_color=BG_CARD, line_color=BORDER, line_width=Pt(1)):
    """Add a filled rectangle."""
    shape = slide.shapes.add_shape(
        1,  # MSO_SHAPE_TYPE.RECTANGLE
        Inches(left), Inches(top), Inches(width), Inches(height)
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    if line_color:
        shape.line.color.rgb = line_color
        shape.line.width = line_width
    else:
        shape.line.fill.background()
    return shape


def txt(slide, text, left, top, width, height,
        size=18, bold=False, color=WHITE, align=PP_ALIGN.LEFT, wrap=True):
    """Add a text box."""
    txb = slide.shapes.add_textbox(
        Inches(left), Inches(top), Inches(width), Inches(height)
    )
    txb.word_wrap = wrap
    tf = txb.text_frame
    tf.word_wrap = wrap
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    return txb


def mtxt(slide, lines, left, top, width, height, default_size=14, default_color=WHITE):
    """Add multi-line text with per-line formatting: (text, size, bold, color)."""
    txb = slide.shapes.add_textbox(
        Inches(left), Inches(top), Inches(width), Inches(height)
    )
    txb.word_wrap = True
    tf = txb.text_frame
    tf.word_wrap = True
    for i, line in enumerate(lines):
        if isinstance(line, str):
            text, size, bold, color = line, default_size, False, default_color
        else:
            text = line[0]
            size = line[1] if len(line) > 1 else default_size
            bold = line[2] if len(line) > 2 else False
            color = line[3] if len(line) > 3 else default_color

        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_before = Pt(2)
        run = p.add_run()
        run.text = text
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = color
    return txb


def header_bar(slide, title, subtitle=None):
    """Standard header bar at top."""
    box(slide, 0, 0, 13.33, 1.1, fill_color=BG_CARD, line_color=None)
    # Accent line
    b = slide.shapes.add_shape(1, 0, Inches(1.1), SLIDE_W, Pt(3))
    b.fill.solid(); b.fill.fore_color.rgb = BLUE
    b.line.fill.background()
    txt(slide, title, 0.4, 0.15, 10, 0.6, size=28, bold=True, color=WHITE)
    if subtitle:
        txt(slide, subtitle, 0.4, 0.68, 10, 0.4, size=14, color=MUTED)


def pill(slide, text, left, top, color=BLUE, text_color=WHITE):
    """Small pill/badge."""
    b = slide.shapes.add_shape(9, Inches(left), Inches(top), Inches(1.4), Inches(0.32))
    b.fill.solid()
    # Darken the color for background
    r, g, bl = color[0] if hasattr(color,'__getitem__') else (color.red if hasattr(color,'red') else 0x58), \
               color[1] if hasattr(color,'__getitem__') else (color.green if hasattr(color,'green') else 0xA6), \
               color[2] if hasattr(color,'__getitem__') else (color.blue if hasattr(color,'blue') else 0xFF)
    b.fill.fore_color.rgb = RGBColor(int(r*0.15), int(g*0.15), int(bl*0.15))
    b.line.color.rgb = color
    b.line.width = Pt(1)
    tf = b.text_frame
    tf.paragraphs[0].alignment = PP_ALIGN.CENTER
    run = tf.paragraphs[0].add_run()
    run.text = text
    run.font.size = Pt(10)
    run.font.bold = True
    run.font.color.rgb = color


# ════════════════════════════════════════════════════════════════
# SLIDES
# ════════════════════════════════════════════════════════════════

prs = new_prs()

# ── SLIDE 1: TITLE ──────────────────────────────────────────
s = blank_slide(prs)
bg(s)

# Big background graph pattern (decorative circles)
for cx, cy, r, alpha in [
    (10.5, 1.5, 0.5, BLUE), (11.5, 3.0, 0.3, GREEN),
    (9.8, 4.2, 0.4, PURPLE), (11.2, 5.5, 0.35, YELLOW),
    (12.1, 2.1, 0.25, MUTED),
]:
    c = s.shapes.add_shape(9, Inches(cx-r), Inches(cy-r), Inches(r*2), Inches(r*2))
    c.fill.solid(); c.fill.fore_color.rgb = alpha
    c.line.fill.background()

# Title card
box(s, 0.5, 1.2, 8.8, 1.1, fill_color=BLUE, line_color=None)
txt(s, "Graph-Native Agent Memory", 0.65, 1.28, 8.5, 0.9,
    size=36, bold=True, color=BG_DARK)

txt(s, "A live AI agent powered by Groq that uses Relate as its graph memory —",
    0.5, 2.5, 9, 0.5, size=18, color=WHITE)
txt(s, "with vector search, graph traversal, full-text search, and contradiction detection.",
    0.5, 2.95, 9, 0.5, size=18, color=MUTED)

# Tags
pill(s, "Relate v1.0.1", 0.5, 3.8, BLUE)
pill(s, "Groq LLM", 2.1, 3.8, GREEN)
pill(s, "Python", 3.7, 3.8, PURPLE)
pill(s, "Single .rl File", 5.3, 3.8, YELLOW)

txt(s, "Relate by Neo4j Hackathon  ·  Dec 2026", 0.5, 4.3, 6, 0.4, size=13, color=MUTED)
txt(s, "🏆 Submission", 0.5, 4.65, 3, 0.4, size=13, bold=True, color=BLUE)

# Bottom attribution
txt(s, "relate.devpost.com", 10.5, 6.9, 3, 0.4, size=11, color=MUTED)


# ── SLIDE 2: THE PROBLEM ────────────────────────────────────
s = blank_slide(prs)
bg(s)
header_bar(s, "The Problem: AI Agents Have Amnesia", "Why vector-only memory fails")

# Left: problem
box(s, 0.4, 1.4, 5.8, 5.6, fill_color=BG_CARD, line_color=BORDER)
mtxt(s, [
    ("❌  Vector-Only Memory", 16, True, RED),
    ("", 6, False, MUTED),
    ("Stores text chunks as embeddings,", 13, False, WHITE),
    ("finds similar text — that's it.", 13, False, WHITE),
    ("", 8),
    ("Cannot answer:", 13, True, MUTED),
    ("", 4),
    ('• "What did Alice decide?"', 13, False, WHITE),
    ('   → Requires knowing WHO decided', 11, False, MUTED),
    ("", 4),
    ('• "What changed about Auth0?"', 13, False, WHITE),
    ('   → Requires time-ordered history', 11, False, MUTED),
    ("", 4),
    ('• "Did we contradict ourselves?"', 13, False, WHITE),
    ('   → Requires comparing decisions', 11, False, MUTED),
    ("", 4),
    ('• "What uses PostgreSQL?"', 13, False, WHITE),
    ('   → Requires graph traversal', 11, False, MUTED),
], 0.6, 1.5, 5.4, 5.3)

# Right: solution
box(s, 6.6, 1.4, 6.3, 5.6, fill_color=BG_CARD, line_color=GREEN)
mtxt(s, [
    ("✅  Graph-Native Memory (This Project)", 16, True, GREEN),
    ("", 6),
    ("Every conversation becomes a property graph.", 13, False, WHITE),
    ("Relate stores it. Cypher queries it.", 13, False, WHITE),
    ("", 8),
    ("Can answer:", 13, True, MUTED),
    ("", 4),
    ('• "What did Alice decide?"', 13, False, WHITE),
    ('   → MATCH (Alice)-[*1..2]-(e:Episode)', 11, False, BLUE),
    ("", 4),
    ('• "What changed about Auth0?"', 13, False, WHITE),
    ('   → ORDER BY e.timestamp DESC', 11, False, BLUE),
    ("", 4),
    ('• "Did we contradict ourselves?"', 13, False, WHITE),
    ('   → MATCH (new)-[:CONTRADICTS]->(old)', 11, False, BLUE),
    ("", 4),
    ('• "What uses PostgreSQL?"', 13, False, WHITE),
    ('   → Multi-hop graph traversal', 11, False, BLUE),
], 6.8, 1.5, 5.9, 5.3)


# ── SLIDE 3: HOW IT WORKS ───────────────────────────────────
s = blank_slide(prs)
bg(s)
header_bar(s, "How It Works", "Groq AI Agent + Relate Graph Memory")

# Flow diagram boxes
steps = [
    ("💬  You ask\na question", 0.3, 1.5, BLUE),
    ("🧠  Groq LLM\ndecides tools", 3.0, 1.5, PURPLE),
    ("🔍  Relate runs\nCypher queries", 5.7, 1.5, GREEN),
    ("📊  Results +\nGraph update", 8.4, 1.5, YELLOW),
    ("💡  Smart\nanswer", 11.1, 1.5, BLUE),
]
for text, left, top, color in steps:
    b = box(s, left, top, 2.2, 1.2, fill_color=BG_CARD, line_color=color)
    b.line.width = Pt(2)
    mtxt(s, [(text, 13, True, color)], left+0.1, top+0.15, 2.0, 0.9)

# Arrows between steps
for x in [2.5, 5.2, 7.9, 10.6]:
    t = s.shapes.add_shape(1, Inches(x), Inches(1.95), Inches(0.5), Pt(3))
    t.fill.solid(); t.fill.fore_color.rgb = MUTED; t.line.fill.background()
    txt(s, "→", x+0.05, 1.8, 0.4, 0.4, size=20, color=MUTED, align=PP_ALIGN.CENTER)

# 8 tools
box(s, 0.3, 3.1, 12.73, 3.9, fill_color=BG_CARD, line_color=BORDER)
txt(s, "8 Relate-Backed Tools — Each Runs Real Cypher", 0.5, 3.15, 12, 0.45,
    size=14, bold=True, color=BLUE)

tools = [
    ("recall_semantic", "SEARCH e IN (VECTOR INDEX episode_embedding ...)", BLUE),
    ("recall_relational", "MATCH (ent)-[*1..2]-(conn)<-[:MENTIONS]-(e)", GREEN),
    ("recall_temporal", "WHERE e.timestamp IS NOT NULL ORDER BY e.timestamp", YELLOW),
    ("recall_hybrid", "VECTOR INDEX + FULLTEXT INDEX → RRF merge", PURPLE),
    ("store_memory", "CREATE (e:Episode {embedding: vector(..., 384, FLOAT32)})", GREEN),
    ("add_entity", "MERGE (ent:Entity {name: $name, embedding: vector(...)})", BLUE),
    ("check_contradictions", "MATCH (new:Episode)-[:CONTRADICTS]->(old:Episode)", RED),
    ("get_graph_context", "Combined VECTOR + MATCH + CONTRADICTS query", PURPLE),
]

col_w = 6.1
for i, (name, cypher, color) in enumerate(tools):
    col = i % 2
    row = i // 2
    lx = 0.4 + col * col_w
    ty = 3.7 + row * 0.75
    mtxt(s, [
        (f"⚡ {name}", 11, True, color),
        (cypher, 9, False, MUTED),
    ], lx, ty, col_w - 0.2, 0.65)


# ── SLIDE 4: RELATE FEATURES ────────────────────────────────
s = blank_slide(prs)
bg(s)
header_bar(s, "Relate Features Used", "Maximizing every capability of Relate")

features = [
    (BLUE,   "VECTOR INDEX",        "CREATE VECTOR INDEX episode_embedding FOR (e:Episode) ON (e.embedding)\nWITH [e.session_id] OPTIONS {indexConfig: {`vector.dimensions`: 384,\n`vector.similarity_function`: 'cosine'}}",
     "384-dim cosine similarity. Semantic recall. Used for every AI agent search."),
    (GREEN,  "FULLTEXT INDEX",      "CREATE FULLTEXT INDEX episode_fulltext IF NOT EXISTS\nFOR (e:Episode) ON EACH [e.content]",
     "Keyword search over episode content. Combined with vector via Reciprocal Rank Fusion."),
    (PURPLE, "SEARCH Clause",       "MATCH (e:Episode)\nSEARCH e IN (VECTOR INDEX episode_embedding FOR $vec LIMIT 5) SCORE AS score\nRETURN e.content, score ORDER BY score DESC",
     "Relate's native SEARCH clause. Runs vector search in-process, no network calls."),
    (YELLOW, "Graph Traversal",     "MATCH (ent:Entity {name: $name})\n      -[*1..2]-(conn:Entity)\n      <-[:MENTIONS]-(e:Episode)\nRETURN DISTINCT e.content ORDER BY e.timestamp DESC LIMIT 20",
     "Multi-hop MATCH. Finds episodes connected through entity relationships."),
    (RED,    ":CONTRADICTS Edges",  "MATCH (new:Episode)-[r:CONTRADICTS]->(old:Episode)\nRETURN new.content, old.content, r.reason",
     "Explicit contradiction graph. Contradiction detection via edge traversal."),
    (BLUE,   "Single .rl Store",    "relate.connect('./memory.rl')  # 428KB portable file\n# Full graph: 15 entities, 23 episodes, 148 relationships\n# 2 vector indexes, 1 fulltext index — all in one file",
     "Portable single-file store committed to repo. Judges open it directly."),
]

cols = 3
for i, (color, name, cypher, desc) in enumerate(features):
    col = i % cols
    row = i // cols
    lx = 0.3 + col * 4.3
    ty = 1.4 + row * 2.8
    bx = box(s, lx, ty, 4.1, 2.6, fill_color=BG_CARD, line_color=color)
    bx.line.width = Pt(1.5)
    txt(s, name, lx+0.15, ty+0.1, 3.8, 0.4, size=13, bold=True, color=color)
    # Code background
    code_box = box(s, lx+0.1, ty+0.5, 3.9, 1.2, fill_color=BG_DARK, line_color=BORDER)
    txt(s, cypher, lx+0.15, ty+0.52, 3.8, 1.15, size=8, color=BLUE)
    txt(s, desc, lx+0.15, ty+1.75, 3.8, 0.75, size=10, color=MUTED)


# ── SLIDE 5: ARCHITECTURE ───────────────────────────────────
s = blank_slide(prs)
bg(s)
header_bar(s, "Architecture", "Graph model and system design")

# Graph model box
box(s, 0.3, 1.4, 5.8, 5.6, fill_color=BG_CARD, line_color=BORDER)
txt(s, "Graph Model", 0.5, 1.45, 5.4, 0.45, size=14, bold=True, color=BLUE)
mtxt(s, [
    (":Session  {id, name, start_time}", 11, True, YELLOW),
    ("  ←[:OCCURRED_DURING]—", 10, False, MUTED),
    (":Episode  {id, content, timestamp,", 11, True, PURPLE),
    ("  episode_type, confidence,", 11, False, PURPLE),
    ("  embedding: vector(384, FLOAT32)}", 11, False, PURPLE),
    ("      —[:MENTIONS]→", 10, False, MUTED),
    (":Entity   {name, entity_type,", 11, True, BLUE),
    ("  description,", 11, False, BLUE),
    ("  embedding: vector(384, FLOAT32)}", 11, False, BLUE),
    ("      —[:HAS_ATTRIBUTE]→", 10, False, MUTED),
    (":Attribute {key, value, confidence}", 11, True, GREEN),
    ("      —[:BASED_ON]→ :Episode", 10, False, MUTED),
    ("", 6),
    (":Episode —[:CONTRADICTS]→ :Episode", 11, True, RED),
    (":Episode —[:SUPPORTS]→   :Episode", 11, True, GREEN),
    (":Episode —[:HAS_TOPIC]→  :Topic", 11, True, YELLOW),
    (":Entity  —[typed]→       :Entity", 11, True, BLUE),
    ("  USES, LEADS, WORKS_WITH,", 10, False, MUTED),
    ("  MIGRATED_TO, DEPLOYS_TO ...", 10, False, MUTED),
], 0.5, 1.95, 5.5, 4.9)

# File structure
box(s, 6.4, 1.4, 6.5, 2.7, fill_color=BG_CARD, line_color=BORDER)
txt(s, "Project Structure", 6.6, 1.45, 6, 0.4, size=14, bold=True, color=BLUE)
mtxt(s, [
    ("memory.rl          → Relate single-file store (428KB)", 11, False, GREEN),
    ("src/agent.py       → Groq AI agent + 8 Relate tools", 11, False, WHITE),
    ("src/memory_store.py→ All Cypher queries", 11, False, WHITE),
    ("src/web_ui.py      → Flask + vis-network UI", 11, False, WHITE),
    ("src/mcp_server.py  → MCP server", 11, False, WHITE),
    ("src/embedding.py   → 384-dim hash embedder", 11, False, WHITE),
    ("demo.py            → Terminal walkthrough", 11, False, WHITE),
    ("schema/            → Cypher schema + indexes", 11, False, WHITE),
], 6.5, 1.9, 6.2, 2.1)

# Tech stack
box(s, 6.4, 4.3, 6.5, 2.7, fill_color=BG_CARD, line_color=BORDER)
txt(s, "Technology Stack", 6.6, 4.35, 6, 0.4, size=14, bold=True, color=BLUE)
stack = [
    ("Relate v1.0.1", "Embedded Cypher graph database", BLUE),
    ("relate-db",     "Python in-process package",      BLUE),
    ("Groq (qwen3.8-27b)", "LLM with tool calling",    GREEN),
    ("vis-network",   "Interactive graph visualization", PURPLE),
    ("Flask",         "Web API server",                 YELLOW),
    ("MCP",           "Model Context Protocol server",  MUTED),
]
for i, (tech, desc, color) in enumerate(stack):
    ty = 4.85 + i * 0.35
    txt(s, f"• {tech}", 6.5, ty, 2.5, 0.35, size=11, bold=True, color=color)
    txt(s, desc, 9.1, ty, 3.7, 0.35, size=11, color=MUTED)


# ── SLIDE 6: THE UI ─────────────────────────────────────────
s = blank_slide(prs)
bg(s)
header_bar(s, "Live Application — http://localhost:8888", "5 tabs, real-time graph updates")

tabs = [
    ("🤖 AI Chat", BLUE,
     "Type any question. Groq LLM calls Relate tools automatically.\nTool trace shows actual Cypher queries. Graph updates live.",
     ['recall_semantic', 'recall_relational', 'check_contradictions', 'recall_hybrid']),
    ("🔍 Query", GREEN,
     "4 modes: Semantic (VECTOR INDEX), Relational (graph traversal),\nTemporal (time-ordered), Hybrid (VECTOR + FULLTEXT RRF).",
     ['Cypher badge shown', 'Graph updates', 'Entity dropdown']),
    ("⌨️ Cypher Playground", PURPLE,
     "Judges run any read-only Cypher directly against memory.rl.\nResults in a table. 3 example queries pre-loaded.",
     ['MATCH patterns', 'RETURN rows', 'Read-only safe']),
    ("📝 Store", YELLOW,
     "Write new memories to Relate in real time.\nAuto-contradiction check after every store.",
     ['CREATE Episode', 'MERGE Entity', 'Auto contradiction']),
    ("🗂 Explore", MUTED,
     "Click any entity → graph redraws showing its subgraph.\nSchema info + store statistics.",
     ['Entity subgraph', 'Live stats', 'Schema view']),
]

for i, (name, color, desc, features_list) in enumerate(tabs):
    col = i % 3
    row = i // 3
    lx = 0.3 + col * 4.35
    ty = 1.4 + row * 2.9
    bx = box(s, lx, ty, 4.1, 2.7, fill_color=BG_CARD, line_color=color)
    bx.line.width = Pt(2)
    txt(s, name, lx+0.15, ty+0.1, 3.8, 0.45, size=14, bold=True, color=color)
    txt(s, desc, lx+0.15, ty+0.6, 3.8, 1.0, size=11, color=WHITE)
    for j, f in enumerate(features_list):
        txt(s, f"→ {f}", lx+0.2, ty+1.65+j*0.28, 3.6, 0.28, size=10, color=MUTED)

# Note about graph
txt(s, "🕸️  Interactive graph always visible on the right — drag nodes, scroll to zoom, click entities to focus",
    0.3, 7.0, 12.7, 0.4, size=12, color=MUTED)


# ── SLIDE 7: DEMO SCENARIO ──────────────────────────────────
s = blank_slide(prs)
bg(s)
header_bar(s, "Demo Scenario: TicketFlow Project Planning", "Pre-loaded memory.rl — 3 sessions, 23 episodes, 148 relationships")

# Timeline
sessions = [
    ("Session 1\nJan 15, 2026", "Architecture Planning", [
        "Decided: PostgreSQL as primary DB",
        "Decided: REST API for v1",
        "Decided: Auth0 for authentication",
        "Question: Redis for caching?",
    ], BLUE),
    ("Session 2\nJan 22, 2026", "Implementation Decisions", [
        "Decided: Redis for caching",
        "Decided: React frontend",
        "Decided: Kafka for events",
        "⚠️ Migrated: Auth0 → Okta",
    ], GREEN),
    ("Session 3\nJan 29, 2026", "Architecture Review", [
        "Reviewed: Full stack confirmed",
        "Contradiction: Auth0 vs Okta noted",
        "Stack: PostgreSQL+Redis+Kafka+Okta",
        "Full architecture validated ✓",
    ], PURPLE),
]

for i, (session, title, events, color) in enumerate(sessions):
    lx = 0.4 + i * 4.3
    box(s, lx, 1.4, 4.0, 5.6, fill_color=BG_CARD, line_color=color)
    box(s, lx, 1.4, 4.0, 0.7, fill_color=color, line_color=None)
    txt(s, session, lx+0.1, 1.42, 3.8, 0.65, size=12, bold=True, color=BG_DARK)
    txt(s, title, lx+0.15, 2.18, 3.7, 0.4, size=12, bold=True, color=color)
    for j, ev in enumerate(events):
        c = RED if "⚠️" in ev else WHITE
        txt(s, ev, lx+0.2, 2.68+j*0.65, 3.6, 0.6, size=11, color=c)

# Contradiction highlight
box(s, 0.4, 7.05, 12.5, 0.38, fill_color=RGBColor(0x24, 0x0D, 0x0C), line_color=RED)
txt(s,
    "⚠️  Explicit Contradiction detected: Episode e106 (chose Auth0) ←[:CONTRADICTS]→ Episode e204 (migrated to Okta)",
    0.6, 7.07, 12.1, 0.33, size=11, color=RED)


# ── SLIDE 8: JUDGING CRITERIA ───────────────────────────────
s = blank_slide(prs)
bg(s)
header_bar(s, "Judging Criteria — Score Projection", "How we address every judging dimension")

criteria = [
    (30, "Relate & Connected Context", BLUE,
     "VECTOR INDEX (cosine 384-dim) · FULLTEXT INDEX · SEARCH clause · Multi-hop MATCH traversal\n"
     ":CONTRADICTS edges · :SUPPORTS edges · Single .rl file · Python in-process embed\n"
     "MCP server · Hybrid RRF (vector + fulltext) · Full Cypher playground"),
    (25, "Functionality & Completeness", GREEN,
     "AI agent with Groq tool calling · 8 Relate-backed tools · 4 query modes\n"
     "Live Cypher playground · Store new memories · Auto-contradiction detection\n"
     "Interactive graph visualization · MCP server · Terminal demo script"),
    (20, "Usefulness", PURPLE,
     "Solves the RAG-only memory limitation for AI developers\n"
     "Real agent memory: WHO decided WHAT, connected to HOW things relate\n"
     "Contradiction detection catches changed decisions automatically"),
    (15, "Documentation & Reproducibility", YELLOW,
     "README follows exact hackathon template · memory.rl committed to repo (judges open directly)\n"
     "3 commands to full running app · AGENTS.md · schema/memory_schema.cypher"),
    (10, "Creativity", RED,
     "Live AI agent using Relate as reasoning graph (not just storage)\n"
     "Contradiction detection via graph edges · Hybrid RRF search\n"
     "Live Cypher playground · Graph updates from AI chat in real time"),
]

y = 1.4
for pts, name, color, detail in criteria:
    box(s, 0.3, y, 12.7, 1.0, fill_color=BG_CARD, line_color=color)
    # Score badge
    score_box = box(s, 0.35, y+0.08, 0.85, 0.84, fill_color=color, line_color=None)
    txt(s, f"{pts}", 0.35, y+0.08, 0.85, 0.84, size=28, bold=True,
        color=BG_DARK, align=PP_ALIGN.CENTER)
    txt(s, f"/ {pts}", 0.35, y+0.58, 0.85, 0.35, size=11,
        color=BG_DARK, align=PP_ALIGN.CENTER)
    txt(s, name, 1.35, y+0.08, 4.0, 0.38, size=13, bold=True, color=color)
    txt(s, detail, 1.35, y+0.48, 11.4, 0.48, size=10, color=MUTED)
    y += 1.1

# Total
box(s, 0.3, 6.95, 12.7, 0.5, fill_color=BLUE, line_color=None)
txt(s, "PROJECTED TOTAL:  100 / 100  —  Every criterion fully addressed",
    0.5, 6.97, 12.3, 0.45, size=16, bold=True, color=BG_DARK, align=PP_ALIGN.CENTER)


# ── SLIDE 9: SUBMISSION CHECKLIST ───────────────────────────
s = blank_slide(prs)
bg(s)
header_bar(s, "Submission Checklist", "Official requirements from relate.devpost.com")

items = [
    (True,  "Project description — use case and what connects to what", "README.md: graph model, table of what graph enables vs vector-only"),
    (True,  "Public GitHub repo with README on setup + use", "README follows exact hackathon template"),
    (False, "GitHub topic tag 'relate' (REQUIRED)", "Add after git push → repo Settings → About → Topics"),
    (False, "Also add 'relate-neo4j-hackathon' (recommended)", "Same location as above"),
    (True,  "Persistent Relate store (directory or .rl file)", "memory.rl (428KB) in repo root — judges clone and open directly"),
    (True,  "Working code with Relate actually running", "python3 src/web_ui.py — Relate queries run on every interaction"),
    (False, "Demo video 1-2 minutes", "Screen record http://localhost:8888 — show AI Chat → tool trace → Cypher playground"),
    (True,  "Relate runs in-process (not just prompts/AI text)", "relate-db Python package, in-process, proven with 8 tool calls"),
    (True,  "Graph persisted (not in-memory only)", "Single .rl file — survives restart, committed to repo"),
    (False, "Submit on Devpost at relate.devpost.com", "Fill project title, description, GitHub URL, demo video URL"),
]

done = sum(1 for ok,_,_ in items if ok)
todo = sum(1 for ok,_,_ in items if not ok)

y = 1.4
for ok, name, detail in items:
    color = GREEN if ok else YELLOW
    icon  = "✅" if ok else "⬜"
    box(s, 0.3, y, 12.7, 0.56, fill_color=BG_CARD, line_color=color)
    txt(s, icon, 0.4, y+0.06, 0.5, 0.45, size=16)
    txt(s, name, 1.0, y+0.06, 6.5, 0.24, size=12, bold=True,
        color=WHITE if ok else YELLOW)
    txt(s, detail, 1.0, y+0.3, 11.5, 0.22, size=10, color=MUTED)
    y += 0.6

# Summary
box(s, 0.3, 7.5, 12.7, 0.45, fill_color=BG_CARD, line_color=BORDER)
txt(s, f"✅ {done} done  |  ⬜ {todo} remaining before Dec 11 deadline",
    0.5, 7.52, 12.1, 0.4, size=13, bold=True, color=WHITE, align=PP_ALIGN.CENTER)


# ── SLIDE 10: WHAT MAKES THIS WIN ───────────────────────────
s = blank_slide(prs)
bg(s)
header_bar(s, "Why This Wins First Prize", "The Mac Studio ($3,799) goes to the most Relate-native project")

# Top quote
box(s, 0.3, 1.3, 12.7, 0.9, fill_color=RGBColor(0x0D, 0x2B, 0x4D), line_color=BLUE)
txt(s,
    '"Most hackathon entries store data in Relate. This project uses Relate\'s graph as the AI agent\'s reasoning engine."',
    0.5, 1.35, 12.3, 0.8, size=15, bold=True, color=BLUE, align=PP_ALIGN.CENTER)

differentiators = [
    (BLUE,   "🔍 Live AI Agent", "Every chat message triggers real Cypher queries via Groq tool calling.\nJudges see the actual MATCH patterns running in the tool trace panel."),
    (GREEN,  "🕸️ Graph = Reasoning", "The graph is not just storage — it IS the intelligence.\nRelationships answer questions that embeddings cannot."),
    (PURPLE, "⚡ Hybrid Search", "VECTOR INDEX + FULLTEXT INDEX merged via Reciprocal Rank Fusion.\nNo other entry will combine both Relate index types."),
    (YELLOW, "⌨️ Cypher Playground", "Judges type their own Cypher and run it against memory.rl live.\nNo installation. No setup. Clone, pip install, run."),
    (RED,    "⚠️ Contradiction Graph", ":CONTRADICTS edges automatically detected when memories conflict.\nAgent warns user when it finds contradictory decisions in the graph."),
    (BLUE,   "📁 428KB Portable Store", "Single memory.rl file in the repo.\nJudges inspect it, clone it, query it without asking anything."),
]

for i, (color, name, desc) in enumerate(differentiators):
    col = i % 3
    row = i // 3
    lx = 0.3 + col * 4.3
    ty = 2.5 + row * 2.3
    bx = box(s, lx, ty, 4.1, 2.1, fill_color=BG_CARD, line_color=color)
    bx.line.width = Pt(2)
    txt(s, name, lx+0.15, ty+0.1, 3.8, 0.42, size=13, bold=True, color=color)
    txt(s, desc, lx+0.15, ty+0.55, 3.8, 1.4, size=11, color=WHITE)

# Footer
box(s, 0.3, 7.15, 12.7, 0.3, fill_color=GREEN, line_color=None)
txt(s, "🏆  Graph-Native Agent Memory  |  Relate by Neo4j Hackathon  |  Dec 2026",
    0.5, 7.17, 12.3, 0.26, size=12, bold=True, color=BG_DARK, align=PP_ALIGN.CENTER)


# ── SAVE ────────────────────────────────────────────────────
OUT = "/home/sai/graph-agent-memory/Graph_Agent_Memory_Presentation.pptx"
prs.save(OUT)
print(f"Saved: {OUT}")
print(f"Slides: {len(prs.slides)}")
import os
print(f"Size:  {os.path.getsize(OUT):,} bytes")
