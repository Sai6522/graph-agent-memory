"""
Groq AI Agent with Relate Graph Memory.

This is the core of the hackathon entry: a real AI agent powered by Groq's
LLM with tool calling, using Relate as its graph memory backend.

The agent has 7 tools backed by Relate:
  - recall_semantic    → VECTOR INDEX search (Cypher SEARCH clause)
  - recall_relational  → multi-hop graph traversal (Cypher MATCH)
  - recall_temporal    → time-ordered queries (Cypher timestamp filter)
  - store_memory       → writes Episode + Entity nodes to Relate
  - add_entity         → creates Entity nodes with embeddings
  - check_contradictions → finds :CONTRADICTS edges
  - get_graph_context  → builds full context window

Every tool call is logged so the UI can show judges what Cypher ran.
"""
import json
import sys
import os
import time
import threading
from typing import List, Dict, Any, Optional, Generator

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from groq import Groq
from src.memory_store import AgentMemory

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "YOUR_GROQ_API_KEY_HERE")
MODEL = "openai/gpt-oss-120b"
MAX_TOOL_ITERATIONS = 6

# ── Tool schemas (what Groq sees) ────────────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "recall_semantic",
            "description": (
                "Search agent memory by semantic similarity using a vector index. "
                "Use this for natural language questions like 'what did we decide about X?', "
                "'what do I know about Y?', or 'find memories related to Z'. "
                "Returns the most relevant episodes with similarity scores."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language search query"},
                    "limit": {"type": "integer", "description": "Max results (default 5)", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall_relational",
            "description": (
                "Traverse the graph to find episodes connected to an entity through relationships. "
                "Use this for questions like 'what did Alice decide?', 'what involves PostgreSQL?', "
                "or 'show me everything connected to X'. Follows entity relationships in the graph."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_name": {"type": "string", "description": "Name of the entity to start from"},
                    "hops": {"type": "integer", "description": "How many relationship hops (1-3, default 2)", "default": 2},
                },
                "required": ["entity_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall_temporal",
            "description": (
                "Find episodes about an entity ordered by time. "
                "Use this for questions like 'what happened to X before Y?', "
                "'what changed about Z over time?', or 'show the history of X'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_name": {"type": "string", "description": "Entity to search about"},
                    "before": {"type": "string", "description": "ISO timestamp — only before this time"},
                    "after":  {"type": "string", "description": "ISO timestamp — only after this time"},
                },
                "required": ["entity_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "store_memory",
            "description": (
                "Store a new memory in the agent's graph. Use this when the user tells you something "
                "new, makes a decision, or shares important information that should be remembered. "
                "The memory is stored as an Episode node with relationships to mentioned entities."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "What to remember"},
                    "episode_type": {
                        "type": "string",
                        "enum": ["message", "decision", "observation", "question"],
                        "description": "Type of memory",
                    },
                    "mentions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Entity names mentioned (people, tools, concepts, projects)",
                    },
                    "confidence": {
                        "type": "number",
                        "description": "Confidence 0.0-1.0 (use 0.9 for decisions, 0.7 for observations)",
                    },
                },
                "required": ["content", "episode_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_entity",
            "description": (
                "Add a new person, technology, concept, or project to the memory graph. "
                "Use this when the user mentions something important that should be tracked as an entity."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Entity name"},
                    "entity_type": {
                        "type": "string",
                        "enum": ["Person", "Technology", "Concept", "Project", "Organization"],
                        "description": "Type of entity",
                    },
                    "description": {"type": "string", "description": "Brief description"},
                },
                "required": ["name", "entity_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall_hybrid",
            "description": (
                "Hybrid memory search using BOTH vector similarity (VECTOR INDEX) AND "
                "full-text keyword search (FULLTEXT INDEX), merged via Reciprocal Rank Fusion. "
                "Use this when you want the most comprehensive results — it finds episodes "
                "that are semantically similar AND episodes that contain exact keywords. "
                "More powerful than semantic-only search."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language query for semantic search"},
                    "keywords": {"type": "string", "description": "Keywords for full-text search (defaults to query)"},
                    "limit": {"type": "integer", "description": "Max results (default 6)", "default": 6},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_contradictions",
            "description": (
                "Check if any memories contradict each other. Use this when the user asks "
                "'did we change our mind about X?', 'are there any conflicts?', or "
                "'what decisions were reversed?'. Returns contradictory episode pairs."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_graph_context",
            "description": (
                "Get a comprehensive context window combining semantic recall, relational recall, "
                "and contradiction detection. Use this for complex questions that need full context, "
                "or at the start of a conversation to understand what the agent knows."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What context to build around"},
                    "limit": {"type": "integer", "description": "Max episodes per recall mode", "default": 4},
                },
                "required": ["query"],
            },
        },
    },
]

# Cypher shown to users for each tool call
TOOL_CYPHER = {
    "recall_semantic": lambda args: (
        f"MATCH (e:Episode)\n"
        f"SEARCH e IN (VECTOR INDEX episode_embedding\n"
        f"  FOR $embedding LIMIT {args.get('limit',5)}) SCORE AS score\n"
        f"RETURN e.id, e.content, score\n"
        f"ORDER BY score DESC"
    ),
    "recall_relational": lambda args: (
        f"MATCH (ent:Entity {{name: \"{args.get('entity_name','')}\"}})\n"
        f"      -[*1..{args.get('hops',2)}]-(connected:Entity)\n"
        f"      <-[:MENTIONS]-(e:Episode)\n"
        f"RETURN DISTINCT e.content, connected.name\n"
        f"ORDER BY e.timestamp DESC LIMIT 20"
    ),
    "recall_hybrid": lambda args: (
        f"// Hybrid: VECTOR INDEX + FULLTEXT INDEX → Reciprocal Rank Fusion\n"
        f"MATCH (e:Episode)\n"
        f"SEARCH e IN (VECTOR INDEX episode_embedding FOR $embedding LIMIT 6) SCORE AS v\n"
        f"WITH e, v\n"
        f"SEARCH e IN (FULLTEXT INDEX episode_fulltext FOR \"{args.get('keywords', args.get('query',''))}\" LIMIT 6) SCORE AS ft\n"
        f"RETURN e.content, v AS vector_score, ft AS text_score\n"
        f"ORDER BY (v + ft) DESC"
    ),
    "recall_temporal": lambda args: (
        f"MATCH (e:Episode)-[:MENTIONS]->\n"
        f"      (Entity {{name: \"{args.get('entity_name','')}\"}})\n"
        f"WHERE e.timestamp IS NOT NULL\n"
        f"RETURN e.content, e.timestamp, e.episode_type\n"
        f"ORDER BY e.timestamp DESC"
    ),
    "store_memory": lambda args: (
        f"CREATE (e:Episode {{\n"
        f"  id: $id, content: \"{args.get('content','')[:40]}...\",\n"
        f"  episode_type: \"{args.get('episode_type','message')}\",\n"
        f"  confidence: {args.get('confidence', 0.8)},\n"
        f"  embedding: vector($emb, 384, FLOAT32)\n"
        f"}})\n"
        f"MERGE (e)-[:OCCURRED_DURING]->(:Session {{id: $session}})"
    ),
    "add_entity": lambda args: (
        f"MERGE (e:Entity {{name: \"{args.get('name','')}\"}})\n"
        f"SET e.entity_type = \"{args.get('entity_type','')}\",\n"
        f"    e.description = \"{args.get('description','')}\",\n"
        f"    e.embedding = vector($emb, 384, FLOAT32)"
    ),
    "check_contradictions": lambda args: (
        "MATCH (new:Episode)-[r:CONTRADICTS]->(old:Episode)\n"
        "RETURN new.content AS new_content, old.content AS old_content,\n"
        "       new.timestamp, r.reason\n"
        "ORDER BY new.timestamp DESC"
    ),
    "get_graph_context": lambda args: (
        f"// Combined semantic + relational + contradiction query\n"
        f"MATCH (e:Episode)\n"
        f"SEARCH e IN (VECTOR INDEX episode_embedding\n"
        f"  FOR $embedding LIMIT {args.get('limit',4)}) SCORE AS score\n"
        f"OPTIONAL MATCH (e)-[:MENTIONS]->(ent:Entity)\n"
        f"OPTIONAL MATCH (e)-[:CONTRADICTS]->(old:Episode)\n"
        f"RETURN e, ent, old ORDER BY score DESC"
    ),
}


class MemoryAgent:
    """AI agent powered by Groq LLM with Relate graph memory tools."""

    def __init__(self, store_path: str = "./memory.rl"):
        self.client = Groq(api_key=GROQ_API_KEY)
        self.memory = AgentMemory(store_path)
        self.session_id = f"agent-{int(time.time())}"
        self.tool_log: List[Dict] = []  # logged for UI display

        # Ensure there's a session in Relate
        self.memory.create_session(
            self.session_id, "AI Agent Chat Session",
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )

    def _execute_tool(self, name: str, args: Dict) -> Dict[str, Any]:
        """Execute a tool against the Relate graph store."""
        try:
            if name == "recall_semantic":
                results = self.memory.recall_semantic(
                    args["query"], args.get("limit", 5)
                )
                return {"results": results, "count": len(results)}

            elif name == "recall_relational":
                results = self.memory.recall_relational(
                    args["entity_name"], args.get("hops", 2)
                )
                return {"results": results, "count": len(results)}

            elif name == "recall_hybrid":
                results = self.memory.recall_hybrid(
                    args["query"], args.get("keywords"), args.get("limit", 6)
                )
                return {"results": results, "count": len(results)}

            elif name == "recall_temporal":
                results = self.memory.recall_temporal(
                    args["entity_name"],
                    before_timestamp=args.get("before"),
                    after_timestamp=args.get("after"),
                )
                return {"results": results, "count": len(results)}

            elif name == "store_memory":
                eid = f"e{int(time.time() * 1000)}"
                self.memory.store_episode(
                    eid, self.session_id,
                    args["content"],
                    time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    episode_type=args.get("episode_type", "message"),
                    mentions=args.get("mentions"),
                    confidence=args.get("confidence", 0.8),
                )
                return {"stored": True, "episode_id": eid, "content": args["content"]}

            elif name == "add_entity":
                result = self.memory.add_entity(
                    args["name"],
                    args["entity_type"],
                    args.get("description", ""),
                )
                return {"added": True, **result}

            elif name == "check_contradictions":
                results = self.memory.detect_contradictions()
                explicit = [r for r in results if r.get("contradiction_type") == "explicit"]
                return {"contradictions": explicit, "count": len(explicit)}

            elif name == "get_graph_context":
                context = self.memory.get_context(args["query"], args.get("limit", 4))
                return {"context": context}

            else:
                return {"error": f"Unknown tool: {name}"}

        except Exception as e:
            return {"error": str(e)}

    def chat(self, user_message: str, conversation_history: List[Dict]) -> Generator:
        """
        Run the agent loop. Yields events as SSE-compatible dicts:
          {"type": "tool_start", "tool": name, "args": {...}, "cypher": "..."}
          {"type": "tool_result", "tool": name, "result": {...}}
          {"type": "text_delta", "content": "..."}
          {"type": "done", "tool_log": [...]}
        """
        self.tool_log = []

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an AI assistant with a graph-based memory powered by Relate, "
                    "an embedded Cypher graph database. Your memory stores episodes (conversations, "
                    "decisions, observations) and entities (people, technologies, concepts, projects) "
                    "as a connected graph.\n\n"
                    "ALWAYS use your memory tools to:\n"
                    "1. Search for relevant past context BEFORE answering any question\n"
                    "2. Store important new information the user shares\n"
                    "3. Detect contradictions when you notice conflicting information\n"
                    "4. Traverse entity relationships to find connected context\n\n"
                    "When you use memory tools, you are running real Cypher queries against "
                    "a Relate graph database — this is graph-native AI memory, not just a vector store.\n\n"
                    "Be helpful and conversational. When you recall memories, explain what you found "
                    "in the graph and how the facts connect to each other."
                ),
            }
        ] + conversation_history + [{"role": "user", "content": user_message}]

        # Agentic loop
        for iteration in range(MAX_TOOL_ITERATIONS):
            response = self.client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.3,
                max_tokens=800,
            )

            msg = response.choices[0].message
            finish = response.choices[0].finish_reason

            # If model wants to call tools
            if finish == "tool_calls" and msg.tool_calls:
                messages.append(msg)

                for tc in msg.tool_calls:
                    tool_name = tc.function.name
                    tool_args = json.loads(tc.function.arguments)
                    cypher = TOOL_CYPHER.get(tool_name, lambda a: "")(tool_args)

                    # Yield tool_start event
                    log_entry = {
                        "tool": tool_name,
                        "args": tool_args,
                        "cypher": cypher,
                    }
                    yield {"type": "tool_start", **log_entry}

                    # Execute against Relate
                    result = self._execute_tool(tool_name, tool_args)
                    log_entry["result"] = result
                    self.tool_log.append(log_entry)

                    yield {"type": "tool_result", "tool": tool_name, "result": result}

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tool_name,
                        "content": json.dumps(result),
                    })

            else:
                # Final answer — stream it
                content = msg.content or ""
                # Yield in chunks to simulate streaming
                chunk_size = 4
                for i in range(0, len(content), chunk_size):
                    yield {"type": "text_delta", "content": content[i:i+chunk_size]}
                    time.sleep(0.01)

                yield {"type": "done", "tool_log": self.tool_log}
                return

        # Fallback if loop exhausted
        yield {"type": "text_delta", "content": "I've searched your memory graph. Let me summarize what I found."}
        yield {"type": "done", "tool_log": self.tool_log}

    def close(self):
        if self.memory:
            self.memory.close()
