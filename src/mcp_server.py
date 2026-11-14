"""
MCP Server for Graph-Native Agent Memory.

Exposes memory operations as MCP tools so AI agents can store and recall
memories through the Model Context Protocol.

Usage:
    python3 src/mcp_server.py [--store ./memory.rl]

Connect from any MCP-compatible client (Claude Desktop, Cursor, etc.)
by pointing its stdio transport at this script.
"""
import sys
import os
import json
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
import mcp.server

from src.memory_store import AgentMemory

STORE_PATH = os.environ.get("MEMORY_STORE", "./memory.rl")

# Global memory store
_mem: AgentMemory = None

server = Server("agent-memory")


def get_memory() -> AgentMemory:
    global _mem
    if _mem is None:
        _mem = AgentMemory(STORE_PATH)
    return _mem


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="store_episode",
            description="Store a new memory episode (conversation turn, decision, or observation) in the agent memory graph.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "The text content of the episode"},
                    "episode_type": {"type": "string", "enum": ["message", "decision", "observation", "question"],
                                     "description": "Type of episode", "default": "message"},
                    "mentions": {"type": "array", "items": {"type": "string"},
                                 "description": "Entity names mentioned in this episode"},
                    "session_id": {"type": "string", "description": "Session ID (defaults to 'default')"},
                    "confidence": {"type": "number", "description": "Confidence 0.0-1.0 (default 1.0)"},
                    "topics": {"type": "array", "items": {"type": "string"},
                               "description": "Topic tags for this episode"},
                },
                "required": ["content"],
            },
        ),
        Tool(
            name="recall_semantic",
            description="Search agent memory by semantic similarity. Returns the most relevant episodes for a given query.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language query to search for"},
                    "limit": {"type": "integer", "description": "Max results (default 5)", "default": 5},
                    "session_filter": {"type": "string", "description": "Optional: filter to a specific session"},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="recall_relational",
            description="Recall episodes connected to an entity through graph relationships. Finds episodes mentioning entities connected to the given entity.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_name": {"type": "string", "description": "Name of the entity to start traversal from"},
                    "hops": {"type": "integer", "description": "How many relationship hops to traverse (default 2)", "default": 2},
                },
                "required": ["entity_name"],
            },
        ),
        Tool(
            name="recall_temporal",
            description="Recall episodes about an entity within a time range. Useful for 'what did we decide before/after X?'",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_name": {"type": "string", "description": "Entity to recall about"},
                    "before": {"type": "string", "description": "ISO timestamp: only episodes before this time"},
                    "after": {"type": "string", "description": "ISO timestamp: only episodes after this time"},
                },
                "required": ["entity_name"],
            },
        ),
        Tool(
            name="check_contradictions",
            description="Detect contradictions in agent memory. Returns episodes that contradict each other, both explicit and potential.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="add_entity",
            description="Add a new entity (person, concept, technology, project) to the agent memory graph.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Entity name"},
                    "entity_type": {"type": "string", "description": "Type: Person, Technology, Concept, Project, etc."},
                    "description": {"type": "string", "description": "Description of the entity"},
                },
                "required": ["name", "entity_type"],
            },
        ),
        Tool(
            name="get_context",
            description="Build a context window for an agent prompt. Combines semantic and relational recall with contradiction detection.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The query to build context for"},
                    "limit": {"type": "integer", "description": "Max episodes to return (default 5)", "default": 5},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_schema",
            description="Return the graph schema: node labels and relationship types in the memory store.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="get_stats",
            description="Return statistics about the memory store: counts of nodes and relationships.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    mem = get_memory()

    if name == "store_episode":
        import time
        eid = f"e{int(time.time() * 1000)}"
        sid = arguments.get("session_id", "default")
        ts = arguments.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        result = mem.store_episode(
            eid, sid, arguments["content"], ts,
            episode_type=arguments.get("episode_type", "message"),
            mentions=arguments.get("mentions"),
            confidence=arguments.get("confidence", 1.0),
            topics=arguments.get("topics"),
        )
        return [TextContent(type="text", text=json.dumps({"status": "stored", "episode_id": eid, **result}))]

    elif name == "recall_semantic":
        results = mem.recall_semantic(
            arguments["query"],
            limit=arguments.get("limit", 5),
            session_filter=arguments.get("session_filter"),
        )
        return [TextContent(type="text", text=json.dumps(results, indent=2))]

    elif name == "recall_relational":
        results = mem.recall_relational(
            arguments["entity_name"],
            hops=arguments.get("hops", 2),
        )
        return [TextContent(type="text", text=json.dumps(results, indent=2))]

    elif name == "recall_temporal":
        results = mem.recall_temporal(
            arguments["entity_name"],
            before_timestamp=arguments.get("before"),
            after_timestamp=arguments.get("after"),
        )
        return [TextContent(type="text", text=json.dumps(results, indent=2))]

    elif name == "check_contradictions":
        results = mem.detect_contradictions()
        return [TextContent(type="text", text=json.dumps(results, indent=2))]

    elif name == "add_entity":
        result = mem.add_entity(
            arguments["name"],
            arguments["entity_type"],
            arguments.get("description", ""),
        )
        return [TextContent(type="text", text=json.dumps({"status": "added", **result}))]

    elif name == "get_context":
        context = mem.get_context(arguments["query"], arguments.get("limit", 5))
        return [TextContent(type="text", text=context)]

    elif name == "get_schema":
        schema = mem.get_schema()
        return [TextContent(type="text", text=json.dumps(schema, indent=2))]

    elif name == "get_stats":
        stats = mem.get_stats()
        return [TextContent(type="text", text=json.dumps(stats, indent=2))]

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    global STORE_PATH
    if len(sys.argv) > 1:
        if sys.argv[1] == "--store" and len(sys.argv) > 2:
            STORE_PATH = sys.argv[2]
        elif not sys.argv[1].startswith("--"):
            STORE_PATH = sys.argv[1]

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, mcp.server.InitializationOptions(
            server_name="agent-memory",
            server_version="1.0.0",
            capabilities=server.get_capabilities(
                notification_options=None,
                experimental_capabilities=None,
            ),
        ))


if __name__ == "__main__":
    asyncio.run(main())
