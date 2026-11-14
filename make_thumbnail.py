"""Generate a professional hackathon thumbnail — 1200x800 (3:2 ratio)."""
from PIL import Image, ImageDraw, ImageFont
import os

W, H = 1200, 800
OUT = "/home/sai/graph-agent-memory/thumbnail.png"

BG     = (13,  17,  23)
CARD   = (22,  27,  34)
BORDER = (48,  54,  61)
BLUE   = (88,  166, 255)
GREEN  = (46,  160, 67)
PURPLE = (247, 120, 186)
YELLOW = (210, 153, 34)
RED    = (248, 81,  73)
WHITE  = (230, 237, 243)
MUTED  = (139, 148, 158)

img = Image.new("RGB", (W, H), BG)
draw = ImageDraw.Draw(img)

def font(size, bold=False):
    for p in [
        f"/usr/share/fonts/truetype/liberation/LiberationSans-{'Bold' if bold else 'Regular'}.ttf",
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'Bold' if bold else ''}.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

# ── Background dots ───────────────────────────────────────────
for x in range(0, W, 55):
    for y in range(0, H, 55):
        draw.ellipse([x-1,y-1,x+1,y+1], fill=(25,30,38))

# ── Left blue accent bar ──────────────────────────────────────
draw.rectangle([0, 0, 7, H], fill=BLUE)

# ── Top header bar ─────────────────────────────────────────────
draw.rectangle([0, 0, W, 70], fill=CARD)
draw.rectangle([0, 70, W, 73], fill=BLUE)
draw.text((24, 18), "🏆  Relate by Neo4j Hackathon  2026", font=font(18, True), fill=BLUE)
# live dot
draw.ellipse([W-130, 25, W-114, 41], fill=GREEN)
draw.text((W-104, 22), "LIVE", font=font(16, True), fill=GREEN)

# ── Main title ─────────────────────────────────────────────────
draw.text((30, 90),  "Graph-Native",  font=font(80, True), fill=WHITE)
draw.text((30, 178), "Agent Memory",  font=font(80, True), fill=BLUE)

# ── Sub-tagline ────────────────────────────────────────────────
draw.text((32, 278), "AI memory that knows how facts connect —", font=font(26), fill=MUTED)
draw.text((32, 312), "not just how text sounds similar.",         font=font(26), fill=MUTED)

# ── Feature pills ──────────────────────────────────────────────
pills = [
    ("⚡ VECTOR INDEX",     BLUE,   32,  370),
    ("🔤 FULLTEXT INDEX",   GREEN,  232, 370),
    ("🕸  Graph Traversal", PURPLE, 462, 370),
    ("⚠️  Contradictions",  RED,    682, 370),
    ("🤖 Groq Tool Calling",YELLOW, 32,  424),
    ("📁 Single .rl File",  BLUE,   302, 424),
    ("🔌 MCP Server",       GREEN,  512, 424),
]
for label, color, px, py in pills:
    bgg = (max(0,color[0]//6), max(0,color[1]//6), max(0,color[2]//6))
    f = font(14, True)
    bbox = draw.textbbox((0,0), label, font=f)
    tw = bbox[2]-bbox[0]
    draw.rounded_rectangle([px, py, px+tw+18, py+28], radius=6, fill=bgg, outline=color, width=1)
    draw.text((px+9, py+5), label, font=f, fill=color)

# ── Divider ────────────────────────────────────────────────────
draw.rectangle([32, 468, W-32, 470], fill=BORDER)

# ── Cypher code block ─────────────────────────────────────────
draw.rounded_rectangle([32, 480, 740, 680], radius=8, fill=CARD, outline=BORDER, width=1)
draw.text((48, 490), "// Relate Cypher — runs live on every chat message", font=font(13), fill=MUTED)

code_lines = [
    ("MATCH ",   PURPLE, "MATCH "),
    ("SEARCH ",  BLUE,   "SEARCH "),
    ("MATCH ",   PURPLE, "MATCH "),
    ("WHERE ",   PURPLE, "WHERE "),
    ("RETURN ",  PURPLE, "RETURN "),
]
cypher = [
    [("MATCH ", PURPLE), ("(e:Episode) ", WHITE)],
    [("SEARCH ", BLUE), ("e ", WHITE), ("IN ", PURPLE), ("(VECTOR INDEX ", WHITE), ("episode_embedding ", YELLOW), ("...) ", WHITE), ("SCORE AS ", PURPLE), ("score", GREEN)],
    [("MATCH ", PURPLE), ("(ent:Entity {name: $name}) ", WHITE)],
    [("      ", WHITE), ("-[*1..2]-(conn) ", GREEN), ("<-[:MENTIONS]-(e)", WHITE)],
    [("MATCH ", PURPLE), ("(new)-[:CONTRADICTS]->(old)", RED)],
    [("RETURN ", PURPLE), ("e.content, score ", WHITE), ("ORDER BY ", PURPLE), ("score DESC", YELLOW)],
]
y = 518
for line_parts in cypher:
    x = 48
    for text, color in line_parts:
        f = font(14)
        draw.text((x, y), text, font=f, fill=color)
        bbox = draw.textbbox((0,0), text, font=f)
        x += bbox[2]-bbox[0]
    y += 24

# ── Stats boxes ────────────────────────────────────────────────
stats = [
    ("23",  "Episodes",      BLUE),
    ("15",  "Entities",      GREEN),
    ("148", "Relationships", PURPLE),
    ("8",   "Agent Tools",   YELLOW),
]
bx = 760
for val, label, color in stats:
    draw.rounded_rectangle([bx, 480, bx+100, 580], radius=8, fill=CARD, outline=color, width=2)
    f_big = font(36, True)
    bbox = draw.textbbox((0,0), val, font=f_big)
    tw = bbox[2]-bbox[0]
    draw.text((bx + (100-tw)//2, 496), val, font=f_big, fill=color)
    f_sm = font(13)
    bbox2 = draw.textbbox((0,0), label, font=f_sm)
    tw2 = bbox2[2]-bbox2[0]
    draw.text((bx + (100-tw2)//2, 545), label, font=f_sm, fill=MUTED)
    bx += 112

# Graph visualization (decorative right side)
nodes = [
    (870, 630, 30, BLUE,   "Relate"),
    (980, 580, 20, GREEN,  "Groq"),
    (970, 680, 18, PURPLE, "Memory"),
    (1070, 625, 16, YELLOW, "Cypher"),
    (1140, 570, 14, RED,   "Conflict"),
    (1150, 680, 14, MUTED, "MCP"),
]
edges = [(0,1),(0,2),(0,3),(1,4),(2,5),(3,4),(1,3)]
for a,b in edges:
    draw.line([nodes[a][0],nodes[a][1],nodes[b][0],nodes[b][1]], fill=BORDER, width=2)
for cx,cy,r,color,lbl in nodes:
    draw.ellipse([cx-r-4,cy-r-4,cx+r+4,cy+r+4],
                 fill=(color[0]//8,color[1]//8,color[2]//8))
    draw.ellipse([cx-r,cy-r,cx+r,cy+r], fill=color, outline=CARD, width=2)
    f = font(10)
    bbox = draw.textbbox((0,0), lbl, font=f)
    tw = bbox[2]-bbox[0]
    draw.text((cx-tw//2, cy+r+4), lbl, font=f, fill=MUTED)

# ── Bottom bar ─────────────────────────────────────────────────
draw.rectangle([0, H-72, W, H], fill=CARD)
draw.rectangle([0, H-72, W, H-69], fill=BORDER)

draw.text((24, H-52), "github.com/Sai6522/graph-agent-memory",
          font=font(15), fill=MUTED)
draw.text((24, H-30), "graph-agent-memory.onrender.com",
          font=font(15, True), fill=BLUE)

# Stack badges
stack = [("Relate", BLUE), ("Groq", GREEN), ("Python", YELLOW), ("Flask", PURPLE)]
sx = W - 500
for name, color in stack:
    f = font(14, True)
    bbox = draw.textbbox((0,0), name, font=f)
    tw = bbox[2]-bbox[0]
    bgg = (color[0]//6, color[1]//6, color[2]//6)
    draw.rounded_rectangle([sx, H-56, sx+tw+16, H-34], radius=5, fill=bgg, outline=color, width=1)
    draw.text((sx+8, H-52), name, font=f, fill=color)
    sx += tw + 28

img.save(OUT, quality=95)
print("Saved:", OUT)
print("Dimensions:", img.size)
print("Size:", os.path.getsize(OUT)//1024, "KB")
