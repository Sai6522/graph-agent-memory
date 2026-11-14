"""
Load sample memory data into a persistent .rl store.

This script creates a realistic scenario: a software team planning
a ticket management system across three sessions. It includes
entities, episodes, decisions, a contradiction, and relationships.

Usage:
    python3 src/load_sample_data.py [--store ./memory.rl]

If --store is omitted, uses ./memory.rl by default.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.memory_store import AgentMemory


def load_sample_data(store_path: str = "./memory.rl"):
    """Create and populate a Relate store with sample agent memory data."""

    # Remove existing store to start fresh
    if os.path.exists(store_path):
        os.remove(store_path)

    mem = AgentMemory(store_path)

    # ════════════════════════════════════════════════════════════════
    # ENTITIES — People, Technologies, Concepts
    # ════════════════════════════════════════════════════════════════
    entities = [
        ("Alice Chen", "Person", "Team lead and backend engineer"),
        ("Bob Martinez", "Person", "Frontend engineer"),
        ("Carol Park", "Person", "DevOps engineer"),
        ("David Kim", "Person", "Product manager"),
        ("TicketFlow", "Project", "The ticket management system being built"),
        ("PostgreSQL", "Technology", "Relational database"),
        ("Redis", "Technology", "In-memory cache and session store"),
        ("Kafka", "Technology", "Event streaming platform"),
        ("REST API", "Concept", "RESTful API design"),
        ("GraphQL", "Concept", "GraphQL API alternative"),
        ("React", "Technology", "Frontend framework"),
        ("Kubernetes", "Technology", "Container orchestration"),
        ("Auth0", "Technology", "Third-party authentication provider"),
        ("Okta", "Technology", "Enterprise identity provider"),
        ("Helm", "Technology", "Kubernetes package manager"),
    ]

    for name, etype, desc in entities:
        mem.add_entity(name, etype, desc)

    # ════════════════════════════════════════════════════════════════
    # RELATIONSHIPS — How entities connect
    # ════════════════════════════════════════════════════════════════
    relationships = [
        ("Alice Chen", "TicketFlow", "LEADS", {"role": "tech_lead"}),
        ("Bob Martinez", "TicketFlow", "WORKS_ON", {"role": "frontend"}),
        ("Carol Park", "TicketFlow", "WORKS_ON", {"role": "devops"}),
        ("David Kim", "TicketFlow", "MANAGES", {"role": "product"}),
        ("TicketFlow", "PostgreSQL", "USES", {}),
        ("TicketFlow", "Redis", "USES", {}),
        ("TicketFlow", "Kafka", "USES", {}),
        ("TicketFlow", "React", "USES", {}),
        ("TicketFlow", "Kubernetes", "DEPLOYS_TO", {}),
        ("PostgreSQL", "Redis", "CACHED_BY", {}),
        ("Kafka", "PostgreSQL", "FEEDS_INTO", {}),
        ("Auth0", "Okta", "MIGRATED_TO", {}),
        ("Helm", "Kubernetes", "PACKAGES_FOR", {}),
    ]

    for source, target, rel, props in relationships:
        mem.relate_entities(source, target, rel, props)

    # ════════════════════════════════════════════════════════════════
    # SESSION 1 — Architecture Planning (Jan 15)
    # ════════════════════════════════════════════════════════════════
    mem.create_session(
        "session-1",
        "Architecture Planning Meeting",
        "2026-01-15T10:00:00Z",
        ["Alice Chen", "Bob Martinez", "David Kim"],
    )

    episodes_s1 = [
        ("e101", "session-1", "2026-01-15T10:05:00Z",
         "David opened the meeting: we need to build TicketFlow, a ticket management system for enterprise customers.",
         "message", ["David Kim", "TicketFlow"], None, 1.0, ["planning"]),

        ("e102", "session-1", "2026-01-15T10:12:00Z",
         "Alice proposed PostgreSQL as the primary database for reliability and ACID compliance.",
         "decision", ["Alice Chen", "PostgreSQL", "TicketFlow"], "PostgreSQL", 0.9, ["database", "planning"]),

        ("e103", "session-1", "2026-01-15T10:15:00Z",
         "Bob suggested we also consider GraphQL instead of REST API for the frontend.",
         "message", ["Bob Martinez", "GraphQL", "REST API"], None, 0.7, ["api"]),

        ("e104", "session-1", "2026-01-15T10:20:00Z",
         "Alice decided to go with REST API for now, keep it simple for v1.",
         "decision", ["Alice Chen", "REST API", "GraphQL"], "REST API", 0.85, ["api"]),

        ("e105", "session-1", "2026-01-15T10:25:00Z",
         "David asked: should we use Auth0 for authentication or build our own?",
         "question", ["David Kim", "Auth0"], None, 0.5, ["auth"]),

        ("e106", "session-1", "2026-01-15T10:30:00Z",
         "Alice decided to use Auth0 for authentication to save development time.",
         "decision", ["Alice Chen", "Auth0"], "Auth0", 0.8, ["auth"]),

        ("e107", "session-1", "2026-01-15T10:35:00Z",
         "Carol joined: we should use Kubernetes for deployment and Helm for package management.",
         "message", ["Carol Park", "Kubernetes", "Helm"], None, 0.7, ["deploy"]),

        ("e108", "session-1", "2026-01-15T10:40:00Z",
         "Bob asked: should we use Redis for caching or keep it simple with just PostgreSQL?",
         "question", ["Bob Martinez", "Redis", "PostgreSQL"], None, 0.5, ["database", "caching"]),
    ]

    for eid, sid, ts, content, etype, mentions, decides, conf, topics in episodes_s1:
        mem.store_episode(eid, sid, content, ts, etype, mentions, decides, conf, topics)

    # ════════════════════════════════════════════════════════════════
    # SESSION 2 — Implementation Decisions (Jan 22)
    # ════════════════════════════════════════════════════════════════
    mem.create_session(
        "session-2",
        "Implementation Decisions",
        "2026-01-22T14:00:00Z",
        ["Alice Chen", "Bob Martinez", "Carol Park"],
    )

    episodes_s2 = [
        ("e201", "session-2", "2026-01-22T14:05:00Z",
         "Alice decided to add Redis for caching session data and hot queries.",
         "decision", ["Alice Chen", "Redis", "PostgreSQL"], "Redis", 0.85, ["database", "caching"]),

        ("e202", "session-2", "2026-01-22T14:10:00Z",
         "Bob decided to use React for the frontend with a component library.",
         "decision", ["Bob Martinez", "React"], "React", 0.9, ["frontend"]),

        ("e203", "session-2", "2026-01-22T14:15:00Z",
         "Carol decided to use Kafka for event streaming between services.",
         "decision", ["Carol Park", "Kafka"], "Kafka", 0.8, ["architecture"]),

        ("e204", "session-2", "2026-01-22T14:20:00Z",
         "Alice decided to migrate from Auth0 to Okta because Auth0 pricing doubled and Okta is cheaper for our seat count.",
         "decision", ["Alice Chen", "Auth0", "Okta"], "Okta", 0.85, ["auth"]),

        ("e205", "session-2", "2026-01-22T14:25:00Z",
         "Bob asked: do we still use Auth0 or move to Okta now?",
         "question", ["Bob Martinez", "Auth0", "Okta"], None, 0.3, ["auth"]),

        ("e206", "session-2", "2026-01-22T14:30:00Z",
         "Alice confirmed: we are migrating to Okta, Auth0 stays read-only for 30 days.",
         "message", ["Alice Chen", "Auth0", "Okta"], None, 0.9, ["auth"]),

        ("e207", "session-2", "2026-01-22T14:35:00Z",
         "Carol set up Helm charts for Kubernetes deployment to staging.",
         "message", ["Carol Park", "Helm", "Kubernetes"], None, 0.8, ["deploy"]),

        ("e208", "session-2", "2026-01-22T14:40:00Z",
         "David asked: what about GraphQL, should we revisit that for v2?",
         "question", ["David Kim", "GraphQL", "REST API"], None, 0.4, ["api"]),
    ]

    for eid, sid, ts, content, etype, mentions, decides, conf, topics in episodes_s2:
        mem.store_episode(eid, sid, content, ts, etype, mentions, decides, conf, topics)

    # ════════════════════════════════════════════════════════════════
    # SESSION 3 — Review and Contradiction (Jan 29)
    # ════════════════════════════════════════════════════════════════
    mem.create_session(
        "session-3",
        "Architecture Review",
        "2026-01-29T15:00:00Z",
        ["Alice Chen", "Bob Martinez", "Carol Park", "David Kim"],
    )

    episodes_s3 = [
        ("e301", "session-3", "2026-01-29T15:05:00Z",
         "Alice reviewed the architecture: PostgreSQL, Redis, Kafka, React, Kubernetes, Okta — all in place.",
         "observation", ["Alice Chen", "PostgreSQL", "Redis", "Kafka", "React", "Kubernetes", "Okta", "TicketFlow"],
         None, 0.95, ["review"]),

        ("e302", "session-3", "2026-01-29T15:10:00Z",
         "Bob asked: didn't we decide to use Auth0 for authentication? I see Okta in the config.",
         "question", ["Bob Martinez", "Auth0", "Okta"], None, 0.6, ["auth"]),

        ("e303", "session-3", "2026-01-29T15:15:00Z",
         "Alice clarified: we changed the decision — Auth0 was too expensive, we migrated to Okta in session 2.",
         "message", ["Alice Chen", "Auth0", "Okta"], None, 0.9, ["auth"]),

        # This is the contradiction: Alice originally decided Auth0 (e106),
        # then changed to Okta (e204). The contradiction is intentional
        # to demonstrate the contradiction detection feature.
        ("e304", "session-3", "2026-01-29T15:20:00Z",
         "David noted: we originally chose Auth0 but switched to Okta — that's a contradiction from the original plan.",
         "observation", ["David Kim", "Auth0", "Okta"], None, 0.7, ["auth"]),
    ]

    for eid, sid, ts, content, etype, mentions, decides, conf, topics in episodes_s3:
        mem.store_episode(eid, sid, content, ts, etype, mentions, decides, conf, topics)

    # ════════════════════════════════════════════════════════════════
    # ATTRIBUTES — Facts with provenance
    # ════════════════════════════════════════════════════════════════
    mem.add_attribute("a1", "PostgreSQL", "role", "primary database", 0.9, "e102")
    mem.add_attribute("a2", "Redis", "role", "cache and session store", 0.85, "e201")
    mem.add_attribute("a3", "Kafka", "role", "event streaming", 0.8, "e203")
    mem.add_attribute("a4", "Okta", "role", "authentication provider", 0.85, "e204")
    mem.add_attribute("a5", "Auth0", "role", "previous auth provider (deprecated)", 0.7, "e304")
    mem.add_attribute("a6", "React", "role", "frontend framework", 0.9, "e202")
    mem.add_attribute("a7", "Kubernetes", "role", "deployment platform", 0.8, "e107")
    mem.add_attribute("a8", "REST API", "role", "API style for v1", 0.85, "e104")

    # ════════════════════════════════════════════════════════════════
    # EXPLICIT CONTRADICTION
    # ════════════════════════════════════════════════════════════════
    mem.mark_contradiction("e204", "e106",
        "Originally chose Auth0 (e106), then switched to Okta (e204) due to pricing")

    # ════════════════════════════════════════════════════════════════
    # SUPPORT relationships
    # ════════════════════════════════════════════════════════════════
    mem.mark_support("e201", "e108")  # Redis decision answers Bob's question
    mem.mark_support("e206", "e205")  # Okta confirmation answers Bob's question

    mem.close()

    # Print stats
    verify = AgentMemory(store_path)
    stats = verify.get_stats()
    print(f"Sample data loaded into {store_path}")
    print(f"  Nodes: {stats}")
    print(f"  Store size: {os.path.getsize(store_path)} bytes")

    # Quick verification queries
    print("\n  Semantic recall 'what database did we choose?':")
    for r in verify.recall_semantic("what database did we choose?", limit=3):
        print(f"    [{r['score']:.3f}] {r['content'][:70]}")

    print("\n  Relational recall (Alice Chen, 2 hops):")
    for r in verify.recall_relational("Alice Chen", hops=2)[:3]:
        print(f"    via {r['via_entity']}: {r['content'][:60]}")

    print("\n  Contradictions:")
    for c in verify.detect_contradictions():
        ctype = c.get("contradiction_type", "?")
        print(f"    [{ctype}] {c.get('old_content', c.get('old_id', '?'))[:50]} → {c.get('new_content', c.get('new_id', '?'))[:50]}")

    verify.close()
    return store_path


if __name__ == "__main__":
    store = "./memory.rl"
    if len(sys.argv) > 1:
        if sys.argv[1] == "--store" and len(sys.argv) > 2:
            store = sys.argv[2]
        else:
            store = sys.argv[1]

    load_sample_data(store)
