-- Graph-Native Agent Memory — Schema
-- Run: python3 src/load_schema.py
-- Or load with: relate --database ./memory.rl < schema/memory_schema.cypher

-- Node labels:
--   :Session      — a conversation or work session
--   :Episode     — a single interaction/message/decision in a session
--   :Entity      — a person, concept, tool, system, or project
--   :Attribute   — a fact or property with confidence and provenance
--   :Topic       — a topic tag for episodes
--
-- Relationship types:
--   :MENTIONS          — Episode -> Entity (the episode references this entity)
--   :RELATED_TO        — Entity -> Entity (entities connected, with a relation type)
--   :HAS_ATTRIBUTE     — Entity -> Attribute (an entity has a fact)
--   :OCCURRED_DURING   — Episode -> Session (temporal placement)
--   :NEXT              — Episode -> Episode (ordering within a session)
--   :SUPPORTS          — Episode -> Episode (this episode supports an earlier one)
--   :CONTRADICTS        — Episode -> Episode (this episode contradicts an earlier one)
--   :HAS_TOPIC          — Episode -> Topic (topic classification)
--   :DECIDED_IN         — Entity -> Episode (a decision about this entity was made here)
--   :BASED_ON          — Attribute -> Episode (provenance: this fact was established in this episode)

-- Constraints
CREATE CONSTRAINT session_id_unique IF NOT EXISTS
FOR (s:Session) REQUIRE s.id IS UNIQUE;

CREATE CONSTRAINT episode_id_unique IF NOT EXISTS
FOR (e:Episode) REQUIRE e.id IS UNIQUE;

CREATE CONSTRAINT entity_name_unique IF NOT EXISTS
FOR (ent:Entity) REQUIRE ent.name IS UNIQUE;

CREATE CONSTRAINT attribute_id_unique IF NOT EXISTS
FOR (a:Attribute) REQUIRE a.id IS UNIQUE;

CREATE CONSTRAINT topic_name_unique IF NOT EXISTS
FOR (t:Topic) REQUIRE t.name IS UNIQUE;

-- Indexes for fast lookups
CREATE INDEX episode_timestamp IF NOT EXISTS FOR (e:Episode) ON (e.timestamp);
CREATE INDEX entity_type IF NOT EXISTS FOR (ent:Entity) ON (ent.entity_type);
CREATE INDEX episode_session IF NOT EXISTS FOR (e:Episode) ON (e.session_id);

-- Vector index for semantic recall (episodes)
CREATE VECTOR INDEX episode_embedding IF NOT EXISTS
FOR (e:Episode) ON (e.embedding) WITH [e.session_id]
OPTIONS {indexConfig: {`vector.dimensions`: 384, `vector.similarity_function`: 'cosine'}};

-- Vector index for entity descriptions (semantic entity search)
CREATE VECTOR INDEX entity_embedding IF NOT EXISTS
FOR (ent:Entity) ON (ent.embedding) WITH [ent.entity_type]
OPTIONS {indexConfig: {`vector.dimensions`: 384, `vector.similarity_function`: 'cosine'}};
