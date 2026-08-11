"""MCP server: keyword search over indexed markdown documentation."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from mcp.server import MCPServer

from mcp_docs_search.store import open_connection

if TYPE_CHECKING:
    import sqlite3

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 5
MIN_LIMIT = 1
MAX_LIMIT = 20

_conn: sqlite3.Connection | None = None


def _get_conn() -> sqlite3.Connection:
    if _conn is None:
        raise RuntimeError("Database connection not initialized")
    return _conn


def _clamp_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_LIMIT
    if limit < MIN_LIMIT:
        return MIN_LIMIT
    if limit > MAX_LIMIT:
        return MAX_LIMIT
    return limit


def _coerce_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _row_to_dict(row: tuple[object, ...]) -> dict[str, object]:
    return {
        "chunk_id": str(row[0]),
        "document_path": str(row[1]),
        "heading_path": str(row[2]),
        "content": str(row[3]),
        "score": _coerce_float(row[4]),
    }


def _serialize_results(results: list[tuple[object, ...]]) -> list[dict[str, object]]:
    return [_row_to_dict(row) for row in results]


async def _search_docs(query: str, limit: int = DEFAULT_LIMIT) -> list[dict[str, object]]:
    clamped = _clamp_limit(limit)
    if not query or not query.strip():
        return []
    try:
        results = list(_get_conn().execute(
            """
            SELECT chunk_id, document_path, heading_path, content, bm25(chunks) AS score
            FROM chunks
            WHERE chunks MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, clamped),
        ))
        return _serialize_results(results)
    except Exception as exc:
        logger.error("search_docs failed: %s", exc)
        return [{"error": "Search failed — check server logs for details."}]


async def _list_sources() -> list[dict[str, str]]:
    try:
        docs = list(_get_conn().execute(
            "SELECT path, indexed_at FROM documents ORDER BY path"
        ))
        counts = {
            row[0]: row[1]
            for row in _get_conn().execute(
                "SELECT document_path, COUNT(*) FROM chunks GROUP BY document_path"
            )
        }
        return [
            {
                "path": str(path),
                "indexed_at": str(indexed_at),
                "chunk_count": str(counts.get(path, 0)),
            }
            for path, indexed_at in docs
        ]
    except Exception as exc:
        logger.error("list_sources failed: %s", exc)
        return [{"error": "Failed to list sources — check server logs for details."}]


async def _get_document(path: str) -> str:
    if not path or not path.strip():
        return "Path parameter is required."
    try:
        row = _get_conn().execute(
            "SELECT 1 FROM documents WHERE path = ? LIMIT 1", (path,)
        ).fetchone()
        if row is None:
            return (
                f"Document not found: '{path}'. "
                f"Use list_sources to see available documents."
            )
        chunks = list(_get_conn().execute(
            "SELECT content FROM chunks WHERE document_path = ? ORDER BY chunk_id",
            (path,),
        ))
        return "\n\n".join(str(chunk[0]) for chunk in chunks)
    except Exception as exc:
        logger.error("get_document failed: %s", exc)
        return "Error retrieving document — check server logs for details."


def create_server(db_path: Path) -> MCPServer:
    """Create and configure the MCP server with the given database path.

    Exits with code 1 if the database does not exist or cannot be opened.
    """
    global _conn

    if not db_path.exists():
        msg = (
            f"Database not found: {db_path}. "
            f"Run `mcp-docs-search index ./docs --db {db_path}` first."
        )
        sys.stderr.write(msg + "\n")
        sys.exit(1)

    try:
        _conn = open_connection(str(db_path))
        _conn.execute("PRAGMA query_only = 1")
    except Exception as exc:
        msg = (
            f"Database not found: {db_path}. "
            f"Run `mcp-docs-search index ./docs --db {db_path}` first."
        )
        logger.error("Failed to open database at %s: %s", db_path, exc)
        sys.stderr.write(msg + "\n")
        sys.exit(1)

    server = MCPServer("docs-mcp")

    @server.tool()
    async def search_docs(query: str, limit: int = DEFAULT_LIMIT) -> list[dict[str, object]]:
        """Search indexed markdown documents by keyword using FTS5 full-text search."""
        return await _search_docs(query, limit)

    @server.tool()
    async def list_sources() -> list[dict[str, str]]:
        """List all indexed documents with chunk count and indexing timestamp."""
        return await _list_sources()

    @server.tool()
    async def get_document(path: str) -> str:
        """Retrieve the full content of an indexed document by path."""
        return await _get_document(path)

    return server


def main() -> None:
    db_path = Path("docs.db")
    server = create_server(db_path)
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    server.run()


if __name__ == "__main__":
    main()
