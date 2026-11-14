"""
Graph-Native Agent Memory — Core Memory Store

This module wraps Relate to provide a graph-based memory system for AI agents.
It stores episodes (conversation turns, decisions, observations), entities
(people, concepts, systems), and their relationships as a property graph.

Key capabilities:
  - store_episode: record an interaction with mentioned entities
  - add_entity: create or merge an entity node
  - relate_entities: connect two entities with a typed relationship
  - recall_semantic: vector search for episodes by meaning
  - recall_relational: graph traversal for relationship-based recall
  - recall_temporal: time-ordered recall ("what did we decide before X?")
  - detect_contradictions: find episodes that contradict each other
  - get_context: build a context window for an agent prompt
  - get_schema: return labels and relationship types
"""
import relate
from typing import List, Dict, Any, Optional
from .embedding import embed, DIMENSIONS


class AgentMemory:
    """A graph-based memory store backed by Relate."""

    def __init__(self, store_path: str = ":memory:"):
        """
        Open or create a Relate store.

        Args:
            store_path: ":memory:", a directory path, or a .rl file path.
        """
        self.db = relate.connect(store_path)
        self._init_schema()

    def _init_schema(self):
        """Create indexes and constraints if they don't exist."""
        statements = [
            "CREATE CONSTRAINT session_id_unique IF NOT EXISTS FOR (s:Session) REQUIRE s.id IS UNIQUE",
            "CREATE CONSTRAINT episode_id_unique IF NOT EXISTS FOR (e:Episode) REQUIRE e.id IS UNIQUE",
            "CREATE CONSTRAINT entity_name_unique IF NOT EXISTS FOR (ent:Entity) REQUIRE ent.name IS UNIQUE",
            "CREATE CONSTRAINT attribute_id_unique IF NOT EXISTS FOR (a:Attribute) REQUIRE a.id IS UNIQUE",
            "CREATE CONSTRAINT topic_name_unique IF NOT EXISTS FOR (t:Topic) REQUIRE t.name IS UNIQUE",
            "CREATE INDEX episode_timestamp IF NOT EXISTS FOR (e:Episode) ON (e.timestamp)",
            "CREATE INDEX entity_type IF NOT EXISTS FOR (ent:Entity) ON (ent.entity_type)",
            "CREATE INDEX episode_session IF NOT EXISTS FOR (e:Episode) ON (e.session_id)",
            "CREATE VECTOR INDEX episode_embedding IF NOT EXISTS FOR (e:Episode) ON (e.embedding) WITH [e.session_id] OPTIONS {indexConfig: {`vector.dimensions`: 384, `vector.similarity_function`: 'cosine'}}",
            "CREATE VECTOR INDEX entity_embedding IF NOT EXISTS FOR (ent:Entity) ON (ent.embedding) WITH [ent.entity_type] OPTIONS {indexConfig: {`vector.dimensions`: 384, `vector.similarity_function`: 'cosine'}}",
            "CREATE FULLTEXT INDEX episode_fulltext IF NOT EXISTS FOR (e:Episode) ON EACH [e.content]",
        ]
        for stmt in statements:
            try:
                self.db.execute(stmt)
            except Exception:
                pass  # Already exists or not yet supported

    # ── Write operations ──────────────────────────────────────────

    def create_session(
        self,
        session_id: str,
        name: str,
        start_time: str,
        participants: Optional[List[str]] = None,
    ) -> Dict:
        """Create a conversation session."""
        self.db.execute(
            "MERGE (s:Session {id: $session_id}) "
            "SET s.name = $name, s.start_time = $start_time, "
            "    s.participants = $participants",
            {
                "session_id": session_id,
                "name": name,
                "start_time": start_time,
                "participants": participants or [],
            },
        )
        return {"session_id": session_id, "name": name}

    def add_entity(
        self,
        name: str,
        entity_type: str,
        description: str = "",
        properties: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        """Create or merge an entity (person, concept, system, tool, project)."""
        emb = embed(f"{name} {entity_type} {description}")
        params = {
            "name": name,
            "entity_type": entity_type,
            "description": description,
            "embedding": emb,
        }
        # Merge extra properties into the param dict
        for k, v in (properties or {}).items():
            params[f"prop_{k}"] = v

        # Build SET clause for extra properties
        extra_set = ""
        if properties:
            parts = []
            for k in properties:
                parts.append(f"ent.{k} = $prop_{k}")
            extra_set = ", " + ", ".join(parts)

        self.db.execute(
            f"MERGE (ent:Entity {{name: $name}}) "
            f"SET ent.entity_type = $entity_type, "
            f"    ent.description = $description, "
            f"    ent.embedding = vector($embedding, {DIMENSIONS}, FLOAT32)"
            f"{extra_set}",
            params,
        )
        return {"name": name, "type": entity_type}

    def store_episode(
        self,
        episode_id: str,
        session_id: str,
        content: str,
        timestamp: str,
        episode_type: str = "message",
        mentions: Optional[List[str]] = None,
        decides: Optional[str] = None,
        confidence: float = 1.0,
        topics: Optional[List[str]] = None,
    ) -> Dict:
        """
        Store an episode (a conversation turn, decision, or observation).

        Args:
            episode_id: unique identifier
            session_id: which session this belongs to
            content: the text content of the episode
            timestamp: ISO 8601 timestamp
            episode_type: 'message', 'decision', 'observation', 'question'
            mentions: list of entity names mentioned in this episode
            decides: entity name if this episode makes a decision about an entity
            confidence: 0.0 to 1.0 confidence in this episode's claims
            topics: list of topic names to tag this episode with
        """
        emb = embed(content)

        # Create the episode node
        self.db.execute(
            "CREATE (e:Episode {"
            "  id: $episode_id, session_id: $session_id, "
            "  content: $content, timestamp: $timestamp, "
            "  episode_type: $episode_type, confidence: $confidence, "
            "  embedding: vector($embedding, 384, FLOAT32)"
            "})",
            {
                "episode_id": episode_id,
                "session_id": session_id,
                "content": content,
                "timestamp": timestamp,
                "episode_type": episode_type,
                "confidence": confidence,
                "embedding": emb,
            },
        )

        # Link episode to session
        self.db.execute(
            "MATCH (e:Episode {id: $eid}), (s:Session {id: $sid}) "
            "MERGE (e)-[:OCCURRED_DURING]->(s)",
            {"eid": episode_id, "sid": session_id},
        )

        # Link mentioned entities
        if mentions:
            for entity_name in mentions:
                self.db.execute(
                    "MATCH (e:Episode {id: $eid}), (ent:Entity {name: $name}) "
                    "MERGE (e)-[:MENTIONS]->(ent)",
                    {"eid": episode_id, "name": entity_name},
                )

        # Link decision
        if decides:
            self.db.execute(
                "MATCH (e:Episode {id: $eid}), (ent:Entity {name: $name}) "
                "MERGE (ent)-[:DECIDED_IN]->(e)",
                {"eid": episode_id, "name": decides},
            )

        # Tag with topics
        if topics:
            for topic_name in topics:
                self.db.execute(
                    "MERGE (t:Topic {name: $name}) "
                    "WITH t "
                    "MATCH (e:Episode {id: $eid}) "
                    "MERGE (e)-[:HAS_TOPIC]->(t)",
                    {"name": topic_name, "eid": episode_id},
                )

        return {"episode_id": episode_id, "session_id": session_id}

    def add_attribute(
        self,
        attr_id: str,
        entity_name: str,
        key: str,
        value: str,
        confidence: float = 1.0,
        source_episode_id: Optional[str] = None,
    ) -> Dict:
        """Add a fact/attribute to an entity with provenance."""
        self.db.execute(
            "CREATE (a:Attribute {"
            "  id: $attr_id, key: $key, value: $value, "
            "  confidence: $confidence"
            "})",
            {
                "attr_id": attr_id,
                "key": key,
                "value": value,
                "confidence": confidence,
            },
        )

        self.db.execute(
            "MATCH (a:Attribute {id: $attr_id}), (ent:Entity {name: $name}) "
            "MERGE (ent)-[:HAS_ATTRIBUTE]->(a)",
            {"attr_id": attr_id, "name": entity_name},
        )

        if source_episode_id:
            self.db.execute(
                "MATCH (a:Attribute {id: $attr_id}), (e:Episode {id: $eid}) "
                "MERGE (a)-[:BASED_ON]->(e)",
                {"attr_id": attr_id, "eid": source_episode_id},
            )

        return {"attr_id": attr_id, "entity": entity_name, "key": key, "value": value}

    def relate_entities(
        self,
        source: str,
        target: str,
        relation: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        """Create a typed relationship between two entities."""
        props_str = ""
        params = {"source": source, "target": target}
        if properties:
            parts = []
            for k, v in properties.items():
                params[f"prop_{k}"] = v
                parts.append(f"r.{k} = $prop_{k}")
            props_str = "SET " + ", ".join(parts)

        self.db.execute(
            f"MATCH (a:Entity {{name: $source}}), (b:Entity {{name: $target}}) "
            f"MERGE (a)-[r:{relation}]->(b) "
            f"{props_str}",
            params,
        )
        return {"source": source, "target": target, "relation": relation}

    def mark_contradiction(
        self,
        new_episode_id: str,
        old_episode_id: str,
        reason: str = "",
    ) -> Dict:
        """Mark that one episode contradicts another."""
        self.db.execute(
            "MATCH (new:Episode {id: $new_id}), (old:Episode {id: $old_id}) "
            "MERGE (new)-[r:CONTRADICTS]->(old) "
            "SET r.reason = $reason",
            {"new_id": new_episode_id, "old_id": old_episode_id, "reason": reason},
        )
        return {"contradiction": f"{new_episode_id} contradicts {old_episode_id}"}

    def mark_support(
        self,
        new_episode_id: str,
        old_episode_id: str,
    ) -> Dict:
        """Mark that one episode supports another."""
        self.db.execute(
            "MATCH (new:Episode {id: $new_id}), (old:Episode {id: $old_id}) "
            "MERGE (new)-[:SUPPORTS]->(old)",
            {"new_id": new_episode_id, "old_id": old_episode_id},
        )
        return {"support": f"{new_episode_id} supports {old_episode_id}"}

    # ── Read operations ───────────────────────────────────────────

    def recall_semantic(
        self,
        query: str,
        limit: int = 5,
        session_filter: Optional[str] = None,
    ) -> List[Dict]:
        """
        Vector search for episodes by semantic similarity.
        Finds episodes whose content is most similar to the query.
        """
        query_vec = embed(query)
        params = {"query_vec": query_vec, "limit": limit}

        where_clause = ""
        if session_filter:
            where_clause = f"WHERE e.session_id = $session_filter"
            params["session_filter"] = session_filter

        try:
            results = self.db.execute(
                f"MATCH (e:Episode) "
                f"SEARCH e IN (VECTOR INDEX episode_embedding FOR $query_vec LIMIT $limit) SCORE AS score "
                f"{where_clause} "
                f"RETURN e.id AS id, e.content AS content, e.timestamp AS timestamp, "
                f"      e.episode_type AS type, e.confidence AS confidence, "
                f"      e.session_id AS session, round(score, 4) AS score "
                f"ORDER BY score DESC, e.id",
                params,
            )
        except Exception:
            # Fallback: scan without index (for small datasets or if index not ready)
            results = self._recall_semantic_scan(query_vec, limit, session_filter)

        rows = []
        for row in results:
            rows.append(dict(row))
        return rows

    def _recall_semantic_scan(
        self, query_vec: List[float], limit: int, session_filter: Optional[str]
    ) -> List[Dict]:
        """Fallback semantic search using vector.similarity.cosine without index."""
        params = {"query_vec": query_vec, "limit": limit}
        where_clause = ""
        if session_filter:
            where_clause = "WHERE e.session_id = $session_filter"
            params["session_filter"] = session_filter

        results = self.db.execute(
            f"MATCH (e:Episode) "
            f"{where_clause} "
            f"WITH e, vector.similarity.cosine(e.embedding, $query_vec) AS score "
            f"ORDER BY score DESC LIMIT $limit "
            f"RETURN e.id AS id, e.content AS content, e.timestamp AS timestamp, "
            f"      e.episode_type AS type, e.confidence AS confidence, "
            f"      e.session_id AS session, round(score, 4) AS score",
            params,
        )
        return [dict(row) for row in results]

    def recall_relational(
        self,
        entity_name: str,
        hops: int = 2,
    ) -> List[Dict]:
        """
        Graph traversal for relationship-based recall.
        Given an entity, find all episodes that mention entities
        connected to it within `hops` hops.
        """
        results = self.db.execute(
            f"MATCH (ent:Entity {{name: $name}})"
            f"-[*1..{min(hops, 3)}]-(connected:Entity)"
            f"<-[:MENTIONS]-(e:Episode) "
            f"WHERE e.id IS NOT NULL "
            f"RETURN DISTINCT e.id AS episode_id, e.content AS content, "
            f"      e.timestamp AS timestamp, e.episode_type AS type, "
            f"      connected.name AS via_entity, "
            f"      ent.name AS source_entity "
            f"ORDER BY e.timestamp DESC LIMIT 20",
            {"name": entity_name},
        )
        return [dict(row) for row in results]

    def recall_hybrid(
        self,
        query: str,
        keywords: Optional[str] = None,
        limit: int = 6,
    ) -> List[Dict]:
        """
        Hybrid recall: vector search + full-text search merged via Reciprocal Rank Fusion.
        Uses VECTOR INDEX (semantic) + FULLTEXT INDEX (keyword) in Relate.
        Returns results ranked by combined RRF score.
        """
        query_vec = embed(query)
        kw = keywords or query  # use query words as keyword search too

        # Vector search via SEARCH clause
        vec_results = []
        try:
            rows = self.db.execute(
                "MATCH (e:Episode) "
                "SEARCH e IN (VECTOR INDEX episode_embedding FOR $vec LIMIT $limit) SCORE AS score "
                "RETURN e.id AS id, e.content AS content, e.timestamp AS timestamp, "
                "       e.episode_type AS type, e.confidence AS confidence, "
                "       e.session_id AS session, round(score,4) AS score "
                "ORDER BY score DESC",
                {"vec": query_vec, "limit": limit},
            )
            vec_results = [dict(r) for r in rows]
        except Exception:
            pass

        # Full-text search via SEARCH clause
        ft_results = []
        try:
            # Sanitize for fulltext query
            ft_query = " OR ".join(w for w in kw.lower().split() if len(w) > 3)
            if ft_query:
                rows = self.db.execute(
                    "MATCH (e:Episode) "
                    "SEARCH e IN (FULLTEXT INDEX episode_fulltext FOR $ft LIMIT $limit) SCORE AS score "
                    "RETURN e.id AS id, e.content AS content, e.timestamp AS timestamp, "
                    "       e.episode_type AS type, e.confidence AS confidence, "
                    "       e.session_id AS session, round(score,4) AS score "
                    "ORDER BY score DESC",
                    {"ft": ft_query, "limit": limit},
                )
                ft_results = [dict(r) for r in rows]
        except Exception:
            pass

        # Reciprocal Rank Fusion (k=60 standard constant)
        k = 60
        rrf: Dict[str, Dict] = {}
        for i, r in enumerate(vec_results):
            eid = r["id"]
            rrf[eid] = r.copy()
            rrf[eid]["rrf_score"] = rrf.get(eid, {}).get("rrf_score", 0) + 1 / (k + i + 1)
            rrf[eid]["sources"] = rrf.get(eid, {}).get("sources", []) + ["vector"]

        for i, r in enumerate(ft_results):
            eid = r["id"]
            if eid not in rrf:
                rrf[eid] = r.copy()
                rrf[eid]["rrf_score"] = 0
                rrf[eid]["sources"] = []
            rrf[eid]["rrf_score"] += 1 / (k + i + 1)
            rrf[eid]["sources"].append("fulltext")

        # Sort and return top results
        ranked = sorted(rrf.values(), key=lambda x: x["rrf_score"], reverse=True)
        for r in ranked:
            r["score"] = round(r["rrf_score"], 4)
            r["search_type"] = "+".join(set(r.get("sources", ["vector"])))
        return ranked[:limit]

    def run_cypher(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        """Execute arbitrary read-only Cypher and return rows as dicts."""
        rows = self.db.execute(query, params or {})
        return [dict(r) for r in rows]

    def recall_temporal(
        self,
        entity_name: str,
        before_timestamp: Optional[str] = None,
        after_timestamp: Optional[str] = None,
    ) -> List[Dict]:
        """
        Temporal recall: what was decided about an entity before/after a time?
        """
        conditions = ["e.timestamp IS NOT NULL"]
        params = {"name": entity_name}

        if before_timestamp:
            conditions.append("e.timestamp < $before_ts")
            params["before_ts"] = before_timestamp

        if after_timestamp:
            conditions.append("e.timestamp > $after_ts")
            params["after_ts"] = after_timestamp

        where_clause = " AND ".join(conditions)

        results = self.db.execute(
            f"MATCH (e:Episode)-[:MENTIONS]->(ent:Entity {{name: $name}}) "
            f"WHERE {where_clause} "
            f"RETURN e.id AS id, e.content AS content, e.timestamp AS timestamp, "
            f"      e.episode_type AS type, e.confidence AS confidence, "
            f"      e.session_id AS session "
            f"ORDER BY e.timestamp DESC LIMIT 20",
            params,
        )
        return [dict(row) for row in results]

    def detect_contradictions(self) -> List[Dict]:
        """
        Find episodes that contradict each other.
        Returns explicit contradictions (marked with :CONTRADICTS)
        plus potential contradictions (same entity, opposing claims).
        """
        # Explicit contradictions
        explicit = self.db.execute(
            "MATCH (new:Episode)-[r:CONTRADICTS]->(old:Episode) "
            "RETURN new.id AS new_id, new.content AS new_content, "
            "       new.timestamp AS new_timestamp, "
            "       old.id AS old_id, old.content AS old_content, "
            "       old.timestamp AS old_timestamp, "
            "       r.reason AS reason, 'explicit' AS contradiction_type"
        )

        # Potential contradictions: episodes mentioning the same entity
        # with different episode_types (decision vs question)
        # or same entity with conflicting attributes
        potential = self.db.execute(
            "MATCH (e1:Episode {episode_type: 'decision'})-[:MENTIONS]->(ent:Entity)"
            "<-[:MENTIONS]-(e2:Episode {episode_type: 'decision'}) "
            "WHERE e1.id <> e2.id AND e1.timestamp < e2.timestamp "
            "RETURN e1.id AS old_id, e1.content AS old_content, "
            "       e1.timestamp AS old_timestamp, "
            "       e2.id AS new_id, e2.content AS new_content, "
            "       e2.timestamp AS new_timestamp, "
            "       ent.name AS entity, 'potential' AS contradiction_type "
            "ORDER BY e2.timestamp DESC LIMIT 10"
        )

        results = [dict(row) for row in explicit]
        results.extend([dict(row) for row in potential])
        return results

    def get_entity_graph(self, entity_name: str, hops: int = 2) -> Dict:
        """
        Get the subgraph around an entity for visualization.
        Returns nodes and edges within `hops` of the entity.
        """
        nodes = []
        edges = []

        # Get the entity and its neighbors via any relationship type
        ent_results = self.db.execute(
            f"MATCH (ent:Entity {{name: $name}})"
            f"-[*0..{min(hops, 3)}]-(connected:Entity) "
            f"RETURN DISTINCT connected.name AS name, "
            f"       connected.entity_type AS type, "
            f"       connected.description AS description",
            {"name": entity_name},
        )
        for row in ent_results:
            nodes.append({
                "id": row["name"],
                "label": row["name"],
                "type": row["type"],
                "description": row.get("description", ""),
                "group": "entity",
            })

        # Get relationships between the node set
        node_names = [n["id"] for n in nodes]
        if node_names:
            for row in self.db.execute(
                "MATCH (a:Entity)-[r]->(b:Entity) "
                "WHERE a.name IN $names AND b.name IN $names "
                "RETURN a.name AS source, b.name AS target, type(r) AS rel_type",
                {"names": node_names},
            ):
                edges.append({
                    "source": row["source"],
                    "target": row["target"],
                    "label": row["rel_type"],
                })

        return {"nodes": nodes, "edges": edges}

    def get_full_graph(self) -> Dict:
        """Get the entire graph for visualization."""
        nodes = []
        edges = []

        # Entities
        for row in self.db.execute(
            "MATCH (ent:Entity) RETURN ent.name AS name, ent.entity_type AS type, "
            "       ent.description AS description"
        ):
            nodes.append({
                "id": row["name"],
                "label": row["name"],
                "type": row["type"],
                "group": "entity",
            })

        # Episodes (as smaller nodes)
        for row in self.db.execute(
            "MATCH (e:Episode) RETURN e.id AS id, e.content AS content, "
            "       e.episode_type AS type, e.timestamp AS timestamp LIMIT 50"
        ):
            short = row["content"][:40] + "..." if len(row["content"]) > 40 else row["content"]
            nodes.append({
                "id": row["id"],
                "label": short,
                "type": row["type"],
                "group": "episode",
                "timestamp": row["timestamp"],
            })

        # MENTIONS edges
        for row in self.db.execute(
            "MATCH (e:Episode)-[:MENTIONS]->(ent:Entity) "
            "RETURN e.id AS source, ent.name AS target LIMIT 100"
        ):
            edges.append({
                "source": row["source"],
                "target": row["target"],
                "label": "MENTIONS",
            })

        # RELATED_TO edges
        for row in self.db.execute(
            "MATCH (a:Entity)-[r]->(b:Entity) "
            "RETURN a.name AS source, b.name AS target, type(r) AS rel_type"
        ):
            edges.append({
                "source": row["source"],
                "target": row["target"],
                "label": row["rel_type"],
            })

        return {"nodes": nodes, "edges": edges}

    def get_context(self, query: str, limit: int = 5) -> str:
        """
        Build a context window for an agent prompt.
        Combines semantic recall with relational recall.
        """
        semantic = self.recall_semantic(query, limit=limit)

        context_parts = ["## Semantic recall (most relevant episodes):"]
        for r in semantic:
            confidence_str = f" (confidence: {r.get('confidence', 1.0):.1%})"
            context_parts.append(
                f"- [{r.get('timestamp', '?')}] {r.get('content', '')}{confidence_str}"
            )

        # Try to find entities in the query
        query_lower = query.lower()
        entity_results = self.db.execute(
            "MATCH (ent:Entity) RETURN ent.name AS name, ent.entity_type AS type"
        )
        mentioned_entities = []
        for row in entity_results:
            if row["name"].lower() in query_lower:
                mentioned_entities.append(row["name"])

        if mentioned_entities:
            context_parts.append("\n## Relational recall (connected episodes):")
            for entity in mentioned_entities[:3]:
                relational = self.recall_relational(entity, hops=2)
                for r in relational[:3]:
                    context_parts.append(
                        f"- [{r.get('timestamp', '?')}] {r.get('content', '')}"
                    )

        # Check for contradictions
        contradictions = self.detect_contradictions()
        if contradictions:
            context_parts.append("\n## Known contradictions:")
            for c in contradictions[:3]:
                context_parts.append(
                    f"- {c.get('old_content', '?')} → {c.get('new_content', '?')}"
                )

        return "\n".join(context_parts)

    def get_schema(self) -> Dict:
        """Return the graph schema (labels and relationship types)."""
        labels = []
        for row in self.db.execute("CALL db.labels() YIELD label RETURN label"):
            labels.append(row["label"])

        rel_types = []
        for row in self.db.execute("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType"):
            rel_types.append(row["relationshipType"])

        return {"labels": labels, "relationship_types": rel_types}

    def get_stats(self) -> Dict:
        """Return counts of nodes and relationships."""
        stats = {}
        for row in self.db.execute(
            "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count"
        ):
            stats[row["label"]] = row["count"]

        rel_count = 0
        for row in self.db.execute("MATCH ()-[r]->() RETURN count(r) AS count"):
            rel_count = row["count"]
        stats["relationships"] = rel_count

        return stats

    def close(self):
        """Close the database connection."""
        if self.db:
            self.db.close()
