"""End-to-end smoke client for the MCP server.

Spawns `mcp-docs-search-server` over stdio exactly as an MCP client would,
lists the advertised tools, and calls all three of them. Use it to verify
the server works without wiring it into an editor first:

    uv run mcp-docs-search ./docs --db ./docs.db --rebuild
    uv run python scripts/mcp_smoke.py --db ./docs.db --query "chunking"

Exits non-zero if the handshake fails or a tool does not respond, so it can
be used as a CI check.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


def _render(payload: Any, limit: int = 240) -> str:
    text = str(payload).replace("\n", " ")
    return text if len(text) <= limit else text[:limit] + "..."


async def run(db: Path, query: str) -> int:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_docs_search.server", "--db", str(db)],
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            print(f"tools advertised: {', '.join(names)}")
            missing = {"search_docs", "list_sources", "get_document"} - set(names)
            if missing:
                print(f"FAIL: server did not advertise {sorted(missing)}")
                return 1

            print("\n--- list_sources ---")
            sources = await session.call_tool("list_sources", {})
            print(_render(sources.structured_content))

            print(f"\n--- search_docs({query!r}) ---")
            found = await session.call_tool(
                "search_docs", {"query": query, "limit": 3}
            )
            results = (found.structured_content or {}).get("result", [])
            if not results:
                print("(no matches)")
            for item in results:
                print(f"  {item['heading_path']}  (score {item['score']:.2f})")
                print(f"    {_render(item['content'], 120)}")

            if results:
                first = results[0]["document_path"]
                print(f"\n--- get_document({first!r}) ---")
                doc = await session.call_tool("get_document", {"path": first})
                body = (doc.structured_content or {}).get("result", "")
                print(f"  {len(body)} characters returned")
                print(f"  starts: {_render(body[:160], 160)}")

            print("\n--- get_document(unknown path) ---")
            missing_doc = await session.call_tool(
                "get_document", {"path": "does-not-exist.md"}
            )
            print(f"  {(missing_doc.structured_content or {}).get('result', '')}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="mcp_smoke")
    parser.add_argument("--db", type=Path, default=Path("docs.db"))
    parser.add_argument("--query", default="chunking")
    args = parser.parse_args()

    if not args.db.exists():
        print(
            f"Database not found: {args.db}. "
            f"Run `uv run mcp-docs-search ./docs --db {args.db}` first.",
            file=sys.stderr,
        )
        return 1

    return asyncio.run(run(args.db, args.query))


if __name__ == "__main__":
    sys.exit(main())
