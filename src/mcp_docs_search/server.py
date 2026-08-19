"""MCP server: keyword search over indexed markdown documentation."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import NoReturn, TypedDict

from mcp.server import MCPServer

from mcp_docs_search.store import (
    Connection,
    DocumentInfo,
    ScoredResult,
    StoreError,
    get_chunks,
    list_documents,
    open_connection,
    sanitise_query,
    search_with_score,
)

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 5
MIN_LIMIT = 1
MAX_LIMIT = 20

# Upper bound on what get_document returns in one response, in characters.
# Roughly 12k tokens. A generated API manual can exceed half a megabyte, and
# returning that whole would either overflow the agent's context or cost six
# figures of tokens to answer what one chunk answers. Truncation happens at a
# chunk boundary so the agent never receives a half-sentence.
MAX_DOCUMENT_CHARS = 50_000


class SearchResultItem(TypedDict):
    chunk_id: str
    document_path: str
    heading_path: str
    content: str
    score: float


class SourceInfo(TypedDict):
    path: str
    indexed_at: str
    chunk_count: int


def _clamp_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_LIMIT
    if limit < MIN_LIMIT:
        return MIN_LIMIT
    if limit > MAX_LIMIT:
        return MAX_LIMIT
    return limit


def _scored_to_dict(result: ScoredResult) -> SearchResultItem:
    return SearchResultItem(
        chunk_id=result.chunk_id,
        document_path=result.document_path,
        heading_path=result.heading_path,
        content=result.content,
        score=result.score,
    )


def _doc_to_dict(info: DocumentInfo) -> SourceInfo:
    return SourceInfo(
        path=info.path,
        indexed_at=info.indexed_at,
        chunk_count=info.chunk_count,
    )


async def _search_docs(
    conn: Connection, query: str, limit: int = DEFAULT_LIMIT
) -> list[SearchResultItem]:
    clamped = _clamp_limit(limit)
    if not query or not query.strip():
        return []
    safe_query = sanitise_query(query)
    if not safe_query:
        return []
    try:
        results = search_with_score(conn, safe_query, clamped)
        return [_scored_to_dict(r) for r in results]
    except StoreError as exc:
        logger.error("search_docs failed: %s", exc)
        return []


async def _list_sources(conn: Connection) -> list[SourceInfo]:
    try:
        docs = list_documents(conn)
        return [_doc_to_dict(d) for d in docs]
    except StoreError as exc:
        logger.error("list_sources failed: %s", exc)
        return []


def _assemble_document(chunks: list[str], path: str) -> str:
    """Join chunks into one document, bounded by MAX_DOCUMENT_CHARS.

    Whole chunks are taken until the next one would cross the budget, so the
    text never ends mid-sentence. When anything is left out, the result says
    so and names the alternative, because a silently truncated document is a
    document the agent will quote from as though it were complete.

    Args:
        chunks: The document's chunks, in order.
        path: Document path, used in the truncation notice.

    Returns:
        The document, or its head plus a notice naming what was omitted.
    """
    separator = "\n\n"
    kept: list[str] = []
    used = 0

    for chunk in chunks:
        addition = len(chunk) + (len(separator) if kept else 0)
        if used + addition > MAX_DOCUMENT_CHARS:
            break
        kept.append(chunk)
        used += addition

    if len(kept) == len(chunks):
        return separator.join(chunks)

    omitted_chunks = len(chunks) - len(kept)
    omitted_chars = sum(len(c) for c in chunks[len(kept):])
    notice = (
        f"[truncated: {omitted_chars:,} of "
        f"{sum(len(c) for c in chunks):,} characters omitted, "
        f"{omitted_chunks} of {len(chunks)} sections not shown. "
        f"This document exceeds the {MAX_DOCUMENT_CHARS:,}-character limit "
        f"for get_document. Use search_docs to find the relevant section of "
        f"'{path}' instead of reading it whole.]"
    )

    if not kept:
        return notice

    return separator.join(kept) + separator + notice


async def _get_document(conn: Connection, path: str) -> str:
    if not path or not path.strip():
        return "Path parameter is required. Provide a document path from list_sources."
    try:
        chunks = get_chunks(conn, path)
        if not chunks:
            return (
                f"Document not found: '{path}'. "
                f"Use list_sources to see available documents."
            )
        return _assemble_document(chunks, path)
    except StoreError as exc:
        logger.error("get_document failed: %s", exc)
        return (
            "Search service temporarily unavailable. "
            "Try again or use list_sources to browse documents."
        )


def create_server(db_path: Path) -> MCPServer:
    """Create and configure the MCP server with the given database path.

    Exits with code 1 if the database does not exist or cannot be opened.
    """
    def unusable_database() -> NoReturn:
        sys.stderr.write(
            f"Database not found: {db_path}. "
            f"Run `mcp-docs-search ./docs --db {db_path}` first.\n"
        )
        sys.exit(1)

    if not db_path.exists():
        unusable_database()

    try:
        conn = open_connection(str(db_path))
    except StoreError as exc:
        logger.error("Failed to open database at %s: %s", db_path, exc)
        unusable_database()

    server = MCPServer("mcp-docs-search")

    @server.tool()
    async def search_docs(query: str, limit: int = DEFAULT_LIMIT) -> list[SearchResultItem]:
        """Search indexed markdown documents by keyword using FTS5 full-text search.

        Returns text chunks ranked by relevance, each with its source
        document path, heading hierarchy, and a BM25 score. Use this
        when looking for specific information across the documentation
        and you do not know which file contains the answer. Prefer this
        over get_document for discovery. Results are ordered most
        relevant first; try broader keywords if nothing matches.
        """
        return await _search_docs(conn, query, limit)

    @server.tool()
    async def list_sources() -> list[SourceInfo]:
        """List all indexed documents with their metadata.

        Returns every document path, when it was indexed, and how many
        searchable chunks it contains. Use this to discover what
        documentation is available, to verify a document path before
        calling get_document, or when the agent needs to know the full
        corpus scope before searching.
        """
        return await _list_sources(conn)

    @server.tool()
    async def get_document(path: str) -> str:
        """Retrieve the full content of one indexed document.

        Returns the text of a single document, reconstructed from its
        chunks in order. Use this when the agent needs the full context
        around a search result or already knows exactly which file to
        read. Prefer search_docs when looking for specific information
        without knowing the source file. The path must match exactly
        what list_sources returns.

        Responses are capped at 50,000 characters. A document longer
        than that is cut at a section boundary and ends with a notice
        naming how much was omitted; search_docs is the way to reach
        the rest.
        """
        return await _get_document(conn, path)

    return server


def main() -> None:
    parser = argparse.ArgumentParser(prog="mcp-docs-search-server")
    parser.add_argument("--db", type=Path, default=Path("docs.db"))
    args = parser.parse_args()

    logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    server = create_server(args.db)
    server.run()


if __name__ == "__main__":
    main()
