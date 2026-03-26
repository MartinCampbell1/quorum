"""
MCP Server v2 - Recipes + Sandbox

Два типа тулзов:
  1. Рецепты (recipe_*) - готовые запросы, безопасные, быстрые
  2. Песочница (sandbox_*) - свободные запросы с safety layer

Агент сначала использует рецепты. Если не хватает - идет в песочницу.
"""

import json
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from graph_recipes import RECIPE_CATALOG
from safety_layer import safe_neo4j_query, safe_ch_query


server = Server("smg-tools")


@server.list_tools()
async def list_tools() -> list[Tool]:
    tools = []

    # --- Рецепты ---
    for name, recipe in RECIPE_CATALOG.items():
        properties = {}
        required = []
        for param_name, param_desc in recipe["params"].items():
            is_optional = "(optional)" in param_desc
            properties[param_name] = {
                "type": "string",
                "description": param_desc,
            }
            if not is_optional:
                required.append(param_name)

        tools.append(Tool(
            name=f"recipe_{name}",
            description=f"[RECIPE] {recipe['description']}",
            inputSchema={
                "type": "object",
                "properties": properties,
                "required": required,
            },
        ))

    # --- Песочница ---
    tools.append(Tool(
        name="sandbox_cypher",
        description=(
            "[SANDBOX] Execute a custom Cypher query on Neo4j. "
            "Use ONLY when no recipe fits your needs. "
            "Rules: READ-ONLY, must include LIMIT (max 200), no mutations. "
            "Prefer recipes when possible - they are faster and safer."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "cypher": {
                    "type": "string",
                    "description": "Cypher query. Must be read-only and include LIMIT.",
                },
            },
            "required": ["cypher"],
        },
    ))

    tools.append(Tool(
        name="sandbox_sql",
        description=(
            "[SANDBOX] Execute a custom SQL query on ClickHouse. "
            "Use ONLY when no recipe fits. "
            "Rules: SELECT only, must include LIMIT (max 200)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "SQL SELECT query with LIMIT.",
                },
            },
            "required": ["sql"],
        },
    ))

    # --- Утилиты ---
    tools.append(Tool(
        name="list_recipes",
        description="Show all available recipes with descriptions. Call this first to see what's available before writing custom queries.",
        inputSchema={"type": "object", "properties": {}},
    ))

    tools.append(Tool(
        name="graph_schema",
        description="Get Neo4j graph schema: node labels, relationship types, properties.",
        inputSchema={"type": "object", "properties": {}},
    ))

    tools.append(Tool(
        name="ch_tables",
        description="List all ClickHouse tables and columns.",
        inputSchema={"type": "object", "properties": {}},
    ))

    return tools


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        # --- Рецепты ---
        if name.startswith("recipe_"):
            recipe_name = name[len("recipe_"):]
            recipe = RECIPE_CATALOG.get(recipe_name)
            if not recipe:
                return [TextContent(type="text", text=f"Unknown recipe: {recipe_name}")]

            # Преобразовать строковые аргументы в нужные типы
            kwargs = {}
            for k, v in arguments.items():
                if v is None or v == "":
                    continue
                # Попытаться распарсить числа и списки
                try:
                    kwargs[k] = json.loads(v)
                except (json.JSONDecodeError, TypeError):
                    kwargs[k] = v

            result = recipe["fn"](**kwargs)
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2, default=str),
            )]

        # --- Песочница ---
        elif name == "sandbox_cypher":
            result = safe_neo4j_query(arguments["cypher"])
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2, default=str),
            )]

        elif name == "sandbox_sql":
            result = safe_ch_query(arguments["sql"])
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2, default=str),
            )]

        # --- Утилиты ---
        elif name == "list_recipes":
            catalog = {}
            for rname, recipe in RECIPE_CATALOG.items():
                catalog[rname] = {
                    "description": recipe["description"],
                    "params": recipe["params"],
                }
            return [TextContent(
                type="text",
                text=json.dumps(catalog, indent=2),
            )]

        elif name == "graph_schema":
            from graph_recipes import neo4j_query
            labels = neo4j_query("CALL db.labels() YIELD label RETURN label")
            rels = neo4j_query("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType")
            schema = {
                "labels": [r["label"] for r in labels],
                "relationships": [r["relationshipType"] for r in rels],
            }
            return [TextContent(type="text", text=json.dumps(schema, indent=2))]

        elif name == "ch_tables":
            from graph_recipes import ch_query
            tables = ch_query(
                "SELECT table, name, type FROM system.columns "
                "WHERE database = currentDatabase() ORDER BY table, position"
            )
            by_table = {}
            for row in tables:
                t = row["table"]
                if t not in by_table:
                    by_table[t] = []
                by_table[t].append({"column": row["name"], "type": row["type"]})
            return [TextContent(type="text", text=json.dumps(by_table, indent=2))]

        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {type(e).__name__}: {e}")]


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
