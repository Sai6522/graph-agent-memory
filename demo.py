#!/usr/bin/env python3
"""
Demo script for Graph-Native Agent Memory.

Walks through all the key features:
1. Semantic recall (vector search)
2. Relational recall (graph traversal)
3. Temporal recall (time-ordered queries)
4. Contradiction detection
5. Context building for agent prompts
6. Graph visualization data

Usage:
    python3 demo.py [--store ./memory.rl]

The script prints formatted output that demonstrates each capability.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.memory_store import AgentMemory

STORE_PATH = "./memory.rl"
if "--store" in sys.argv:
    idx = sys.argv.index("--store")
    if idx + 1 < len(sys.argv):
        STORE_PATH = sys.argv[idx + 1]
elif len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
    STORE_PATH = sys.argv[1]


def separator(title):
    print(f"\n{'═' * 70}")
    print(f"  {title}")
    print(f"{'═' * 70}")


def main():
    if not os.path.exists(STORE_PATH):
        print(f"Store not found at {STORE_PATH}. Loading sample data first...")
        from src.load_sample_data import load_sample_data
        load_sample_data(STORE_PATH)

    mem = AgentMemory(STORE_PATH)

    # ════════════════════════════════════════════════════════════════
    separator("GRAPH-NATIVE AGENT MEMORY — DEMO")
    # ════════════════════════════════════════════════════════════════

    stats = mem.get_stats()
    print(f"\nStore: {STORE_PATH}")
    print(f"Size:  {os.path.getsize(STORE_PATH):,} bytes")
    print(f"\nGraph contents:")
    for k, v in stats.items():
        print(f"  {v:>4}  {k}")

    # ════════════════════════════════════════════════════════════════
    separator("1. SEMANTIC RECALL — Vector Search")
    # ════════════════════════════════════════════════════════════════
    print("\nFinds episodes by meaning, not keyword matching.")
    print("Query: 'what database did we choose?'\n")

    results = mem.recall_semantic("what database did we choose?", limit=5)
    for i, r in enumerate(results, 1):
        print(f"  {i}. [{r['score']:.3f}] [{r['timestamp'][:10]}] {r['type']}")
        print(f"     {r['content']}")
    print(f"\n  → Vector search uses Relate's built-in VECTOR INDEX")
    print(f"    with cosine similarity over 384-dimension embeddings.")

    # ════════════════════════════════════════════════════════════════
    separator("2. RELATIONAL RECALL — Graph Traversal")
    # ════════════════════════════════════════════════════════════════
    print("\nFinds episodes through entity relationships (graph traversal).")
    print("Starting entity: 'Alice Chen' — find episodes mentioning connected entities.\n")

    results = mem.recall_relational("Alice Chen", hops=2)
    for i, r in enumerate(results[:5], 1):
        print(f"  {i}. via {r['via_entity']}: [{r['timestamp'][:10]}]")
        print(f"     {r['content']}")
    print(f"\n  → Traverses :WORKS_ON, :LEADS, :USES edges between entities")
    print(f"    to find episodes that mention connected entities.")

    # ════════════════════════════════════════════════════════════════
    separator("3. TEMPORAL RECALL — Time-Ordered Queries")
    # ════════════════════════════════════════════════════════════════
    print("\n'What did we decide about Auth0 before Jan 20?'\n")

    results = mem.recall_temporal("Auth0", before_timestamp="2026-01-20T00:00:00Z")
    for i, r in enumerate(results, 1):
        print(f"  {i}. [{r['timestamp'][:10]}] {r['type']} (confidence: {r['confidence']:.0%})")
        print(f"     {r['content']}")

    print(f"\n  Now: 'What happened with Auth0 after Jan 20?'\n")
    results = mem.recall_temporal("Auth0", after_timestamp="2026-01-20T00:00:00Z")
    for i, r in enumerate(results, 1):
        print(f"  {i}. [{r['timestamp'][:10]}] {r['type']} (confidence: {r['confidence']:.0%})")
        print(f"     {r['content']}")

    # ════════════════════════════════════════════════════════════════
    separator("4. CONTRADICTION DETECTION")
    # ════════════════════════════════════════════════════════════════
    print("\nDetects when later episodes contradict earlier decisions.\n")

    contradictions = mem.detect_contradictions()
    explicit = [c for c in contradictions if c.get("contradiction_type") == "explicit"]
    potential = [c for c in contradictions if c.get("contradiction_type") == "potential"]

    print(f"  Explicit contradictions ({len(explicit)}):")
    for c in explicit:
        print(f"    ⚠️  OLD [{c.get('old_timestamp', '?')[:10]}]: {c.get('old_content', '?')[:60]}")
        print(f"       NEW [{c.get('new_timestamp', '?')[:10]}]: {c.get('new_content', '?')[:60]}")
        if c.get("reason"):
            print(f"       Reason: {c['reason']}")

    print(f"\n  Potential contradictions ({len(potential)}):")
    print(f"    (Multiple decisions about the same entity — may need review)")

    # ════════════════════════════════════════════════════════════════
    separator("5. CONTEXT BUILDING — For Agent Prompts")
    # ════════════════════════════════════════════════════════════════
    print("\nBuilds a context window combining semantic + relational + contradictions.\n")

    context = mem.get_context("what did we decide about authentication?", limit=3)
    print(context)

    # ════════════════════════════════════════════════════════════════
    separator("6. SCHEMA & GRAPH STRUCTURE")
    # ════════════════════════════════════════════════════════════════
    print("\nGraph schema:\n")
    schema = mem.get_schema()
    print(f"  Node labels: {', '.join(schema['labels'])}")
    print(f"  Relationship types: {', '.join(schema['relationship_types'])}")

    print(f"\n  The graph models:")
    print(f"    :Session → :Episode → :Entity (MENTIONS)")
    print(f"    :Entity → :Entity (RELATED_TO, WORKS_WITH, USES, etc.)")
    print(f"    :Entity → :Attribute (HAS_ATTRIBUTE, with confidence + provenance)")
    print(f"    :Episode → :Episode (CONTRADICTS, SUPPORTS)")
    print(f"    :Episode → :Topic (HAS_TOPIC)")
    print(f"    Vector indexes on Episode.embedding and Entity.embedding")

    # ════════════════════════════════════════════════════════════════
    separator("DEMO COMPLETE")
    # ════════════════════════════════════════════════════════════════
    print(f"""
  This demo showed:
    ✓ Semantic recall via vector search (Relate VECTOR INDEX)
    ✓ Relational recall via graph traversal (Cypher MATCH patterns)
    ✓ Temporal recall via timestamp filtering
    ✓ Contradiction detection via :CONTRADICTS edges + graph patterns
    ✓ Context building combining all recall modes
    ✓ Schema introspection

  To explore interactively:
    python3 src/web_ui.py --store {STORE_PATH}

  To serve over MCP for AI agents:
    python3 src/mcp_server.py --store {STORE_PATH}

  To query directly with Cypher:
    relate --database {STORE_PATH} --read-only "MATCH (e:Episode)-[:MENTIONS]->(ent:Entity) RETURN e.content, ent.name LIMIT 10"
""")

    mem.close()


if __name__ == "__main__":
    main()
