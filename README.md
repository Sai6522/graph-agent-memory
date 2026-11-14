# Graph-Native Agent Memory

A graph-based memory system for AI agents that turns every conversation into a queryable property graph — with a **live AI agent powered by Groq** that uses Relate as its memory backend via tool calling.

## Use case

AI agents today use vector-only memory (RAG). They can find *similar* text but cannot answer relationship questions: "What did Alice decide, and does it contradict an earlier decision?" — that requires a graph traversal, not a similarity search.

This project models agent memory as a property graph in Relate. Every conversation turn is an `:Episode` node. Every person, technology, or concept is an `:Entity` node. Episodes connect to entities via `:MENTIONS`. Episodes can `:CONTRADICT` earlier ones. Facts carry confidence scores and provenance edges. The AI agent (Groq LLM with tool calling) uses this graph as its memory — recalling facts, traversing relationships, and detecting contradictions automatically.

**What makes this graph-native (not just vector storage):**

| Question | Vector-only memory | This project |
|----------|-------------------|--------------|
| "What did we decide about databases?" | Similarity search | VECTOR INDEX + SEARCH clause |
| "What involves PostgreSQL and its connected services?" | ❌ | Multi-hop MATCH traversal |
| "What did we decide BEFORE switching to Okta?" | ❌ | Timestamp-ordered Cypher query |
| "Did we contradict an earlier decision?" | ❌ | :CONTRADICTS edge detection |
| "Who is connected to Alice and what did they decide?" | ❌ | Graph traversal + MENTIONS edges |

## How it uses Relate

- **Mode:** single file (`.rl`)
- **Why this mode:** one portable file carries the entire agent memory, committed to the repo, opened by judges without any setup
- **What the graph models:** Sessions, Episodes (with 384-dim vector embeddings), Entities, Attributes with provenance, Topics, and 11 typed relationship types
- **Relate features used:**
  - `CREATE VECTOR INDEX` — episode and entity embeddings (384-dim, cosine)
  - `SEARCH ... IN (VECTOR INDEX ...)` — semantic recall
  - `MATCH (ent)-[*1..2]-(connected)<-[:MENTIONS]-(e)` — relational recall
  - Cypher timestamp filtering — temporal recall
  - `:CONTRADICTS` edges — contradiction detection
  - `CREATE CONSTRAINT ... REQUIRE ... IS UNIQUE` — data integrity
  - Single `.rl` file store — portable, embeddable, no server
  - Python `relate-db` package — in-process graph queries

## Setup and run

**Prerequisites:** Python 3.10+

```bash
git clone <repo>
cd graph-agent-memory
pip install -r requirements.txt
```

**Load sample data** (creates `memory.rl` with 15 entities, 20 episodes, 3 sessions, 11 contradictions):
```bash
python3 src/load_sample_data.py
```

**Run the full application:**
```bash
python3 src/web_ui.py
# Open http://localhost:8080
```

**Run the terminal demo:**
```bash
python3 demo.py
```

**MCP server** (connect from Claude Desktop, Cursor, or any MCP client):
```bash
python3 src/mcp_server.py --store ./memory.rl
```

**Direct Cypher queries** (requires Relate CLI):
```bash
relate --database ./memory.rl --read-only \
  "MATCH (e:Episode)-[:MENTIONS]->(ent:Entity) RETURN e.content, ent.name LIMIT 10"
```

## Where the data lives

The persistent Relate store is at **`./memory.rl`** in the repository root. Judges can open it and query it directly — no setup needed.

## Architecture

```
graph-agent-memory/
├── memory.rl                     # Relate single-file store (pre-loaded, 428KB)
├── requirements.txt
├── demo.py                        # Terminal demo of all features
├── schema/
│   └── memory_schema.cypher       # Constraints, indexes, vector indexes
└── src/
    ├── embedding.py               # Hash-based 384-dim embedder (no API key needed)
    ├── memory_store.py            # AgentMemory class — all Relate queries
    ├── agent.py                   # Groq AI agent with 7 Relate-backed tools
    ├── load_sample_data.py        # Creates and populates memory.rl
    ├── mcp_server.py              # MCP server for agent access
    └── web_ui.py                  # Interactive web app (Flask + vis-network)
```

## The AI agent (Groq + Relate)

The `MemoryAgent` class in `src/agent.py` connects Groq's LLM to Relate via tool calling. The agent has 7 tools, each backed by a real Cypher query:

| Tool | Cypher pattern | What it finds |
|------|---------------|---------------|
| `recall_semantic` | `SEARCH e IN (VECTOR INDEX episode_embedding ...)` | Semantically similar episodes |
| `recall_relational` | `MATCH (ent)-[*1..2]-(connected)<-[:MENTIONS]-(e)` | Graph-connected episodes |
| `recall_temporal` | `WHERE e.timestamp < $before ORDER BY e.timestamp` | Time-ordered episode history |
| `store_memory` | `CREATE (e:Episode {embedding: vector(...)})` | Writes new episode to graph |
| `add_entity` | `MERGE (ent:Entity {name: $name})` | Creates entity node |
| `check_contradictions` | `MATCH (new)-[:CONTRADICTS]->(old)` | Finds conflicting decisions |
| `get_graph_context` | Combined VECTOR + MATCH + CONTRADICTS | Full context window |

## Graph model

```
(:Session {id, name, start_time})
  ←[:OCCURRED_DURING]- (:Episode {id, content, timestamp, episode_type, confidence,
                                    embedding: vector(384, FLOAT32)})
      -[:MENTIONS]→ (:Entity {name, entity_type, description, embedding})
      -[:CONTRADICTS]→ (:Episode)      [with reason]
      -[:SUPPORTS]→ (:Episode)
      -[:HAS_TOPIC]→ (:Topic {name})

(:Entity) -[typed rel]→ (:Entity)      [WORKS_WITH, USES, LEADS, MIGRATED_TO, ...]
(:Entity) -[:HAS_ATTRIBUTE]→ (:Attribute {key, value, confidence})
          -[:BASED_ON]→ (:Episode)      [provenance]
```

## Technologies

- **Relate** (`relate-db`) — embedded Cypher graph database, single-file store, vector search, graph traversal
- **Groq** (`groq`) — LLM API with tool calling (qwen/qwen3.8-27b model)
- **Flask** — web API and UI server
- **vis-network** — interactive graph visualization
- **MCP** — Model Context Protocol server

## License

MIT
