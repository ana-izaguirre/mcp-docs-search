"""SQLite FTS5 storage for document chunks."""

import re
import sqlite3
from pathlib import Path
from typing import NamedTuple

MAX_CONTENT_LENGTH = 50000
MAX_SEARCH_LIMIT = 20

__all__ = [
    "SearchResult",
    "ScoredResult",
    "DocumentInfo",
    "StoreError",
    "Connection",
    "create_tables",
    "open_connection",
    "insert_document",
    "insert_chunk",
    "commit",
    "search",
    "sanitise_query",
    "search_with_score",
    "list_documents",
    "get_chunks",
]

SearchResult = tuple[str, str, str, str]
Connection = sqlite3.Connection


class StoreError(Exception):
    """Raised when the index cannot be read."""


class ScoredResult(NamedTuple):
    chunk_id: str
    document_path: str
    heading_path: str
    content: str
    score: float


class DocumentInfo(NamedTuple):
    path: str
    indexed_at: str
    chunk_count: int


def create_tables(db_path: str) -> Connection:
    """Create the documents and chunks tables.

    Args:
        db_path: Path to the SQLite database file. Must not already exist.

    Returns:
        An open connection to the new database.

    Raises:
        StoreError: If the database file already exists.
    """
    if Path(db_path).exists():
        raise StoreError(
            f"Database already exists: {db_path}. Use --rebuild to recreate it."
        )

    try:
        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            CREATE TABLE documents (
                path TEXT PRIMARY KEY,
                indexed_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE VIRTUAL TABLE chunks USING fts5(
                chunk_id UNINDEXED,
                chunk_index UNINDEXED,
                document_path UNINDEXED,
                heading_path,
                content,
                tokenize='unicode61'
            )
            """
        )
        conn.commit()
    except sqlite3.Error as exc:
        raise StoreError(f"Failed to create database at {db_path}") from exc
    return conn


def open_connection(db_path: str) -> Connection:
    """Open an existing database.

    Raises:
        StoreError: If the database file does not exist.
    """
    if not Path(db_path).exists():
        raise StoreError(
            f"Database not found: {db_path}. "
            f"Run `mcp-docs-search <folder>` first."
        )
    try:
        return sqlite3.connect(db_path)
    except sqlite3.Error as exc:
        raise StoreError(
            f"Database not found: {db_path}. "
            f"Run `mcp-docs-search <folder>` first."
        ) from exc


def insert_document(conn: Connection, path: str, indexed_at: str) -> None:
    """Record an indexed document.

    Args:
        conn: An open database connection.
        path: Document path relative to the indexed root, forward slashes.
        indexed_at: Timestamp of when the document was indexed.

    Raises:
        ValueError: If path or indexed_at is empty.
        StoreError: If the document cannot be recorded.
    """
    if not path or not path.strip():
        raise ValueError("Document path cannot be empty")

    if not indexed_at or not indexed_at.strip():
        raise ValueError("indexed_at cannot be empty")

    try:
        conn.execute(
            """
            INSERT INTO documents (path, indexed_at)
            VALUES (?, ?)
            """,
            (path, indexed_at),
        )
    except sqlite3.Error as exc:
        raise StoreError(f"Failed to record document {path!r}") from exc


def insert_chunk(
    conn: Connection,
    chunk_id: str,
    document_path: str,
    heading_path: str,
    content: str,
    chunk_index: int = 0,
) -> None:
    """Insert a single chunk.

    Args:
        conn: An open database connection.
        chunk_id: Identifier unique across the index.
        document_path: Document path relative to the indexed root.
        heading_path: Full heading path of the chunk.
        content: Chunk body.
        chunk_index: Position of the chunk within its document, counted
            from 0. ``get_chunks`` orders by this, so it is what makes a
            document reconstructable.

    Raises:
        ValueError: If content is empty, exceeds MAX_CONTENT_LENGTH, or
            chunk_index is negative.
        StoreError: If the chunk cannot be written to the index.
    """
    if not content or not content.strip():
        raise ValueError("Cannot insert empty content")

    if len(content) > MAX_CONTENT_LENGTH:
        raise ValueError(
            f"Content too long: {len(content)} characters > {MAX_CONTENT_LENGTH}"
        )

    if chunk_index < 0:
        raise ValueError(f"chunk_index must be >= 0, got {chunk_index}")

    try:
        conn.execute(
            """
            INSERT INTO chunks
                (chunk_id, chunk_index, document_path, heading_path, content)
            VALUES (?, ?, ?, ?, ?)
            """,
            (chunk_id, chunk_index, document_path, heading_path, content),
        )
    except sqlite3.Error as exc:
        raise StoreError(f"Failed to insert chunk into {document_path}") from exc


def commit(conn: Connection) -> None:
    """Commit the open transaction.

    Exists so callers never have to touch ``sqlite3`` themselves: a commit
    can fail (disk full, database locked) and that failure has to reach the
    CLI as a ``StoreError`` like every other storage failure.

    Raises:
        StoreError: If the transaction cannot be committed.
    """
    try:
        conn.commit()
    except sqlite3.Error as exc:
        raise StoreError("Failed to commit the index") from exc


_TOKEN_SANITISER = re.compile(r'[^a-zA-Z0-9._-]')


def sanitise_query(query: str) -> str:
    """Sanitise a user query for safe FTS5 matching.

    Splits on whitespace, strips FTS5 operator characters and punctuation from
    each token, then wraps each surviving term in double quotes. Quotes are
    treated as punctuation and dropped rather than passed through to the FTS5
    parser. Tokens that become empty are discarded; if every token is dropped,
    the result is an empty string.
    """
    terms = query.split()
    cleaned = [_TOKEN_SANITISER.sub('', t) for t in terms]
    surviving = [t for t in cleaned if t]
    quoted = ['"' + t + '"' for t in surviving]
    return " ".join(quoted)


def _run_query(
    conn: Connection, match_expr: str, limit: int
) -> list[ScoredResult]:
    """Execute one FTS5 match and return scored rows, most relevant first.

    ``ORDER BY rank`` is ascending on purpose: ``bm25()`` returns negative
    values where more negative means more relevant.

    Raises:
        StoreError: If the query cannot be executed.
    """
    try:
        cursor = conn.execute(
            """
            SELECT chunk_id, document_path, heading_path, content,
                   bm25(chunks) AS score
            FROM chunks
            WHERE chunks MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (match_expr, limit),
        )
    except sqlite3.Error as exc:
        raise StoreError(f"Search query failed: {match_expr!r}") from exc
    return [ScoredResult(*row) for row in cursor.fetchall()]


def _search(conn: Connection, query: str, limit: int) -> list[ScoredResult]:
    """Sanitise, clamp and run the query, with the AND-then-OR fallback.

    Every search enters here, so sanitising is not something a caller can
    forget: free text becomes literal quoted terms before it reaches FTS5.
    An implicit AND runs first; if no chunk holds every term, the same terms
    are retried joined by ``OR`` so a partial match still returns something.
    """
    if not query or not query.strip():
        return []

    clamped_limit = max(1, min(limit, MAX_SEARCH_LIMIT))

    safe_query = sanitise_query(query)
    if not safe_query:
        return []

    all_terms = _run_query(conn, safe_query, clamped_limit)
    if all_terms:
        return all_terms

    return _run_query(conn, " OR ".join(safe_query.split()), clamped_limit)


def search(conn: Connection, query: str, limit: int = 5) -> list[SearchResult]:
    """Search chunks, ranked by BM25 relevance.

    Args:
        conn: An open database connection.
        query: Free text. Sanitised internally, so FTS5 operators are
            matched as literal words rather than interpreted.
        limit: Maximum number of results, clamped to 1-20.

    Returns:
        A list of (chunk_id, document_path, heading_path, content), most
        relevant first. Empty if the query has no searchable terms.

    Raises:
        StoreError: If the query cannot be executed.
    """
    return [
        (r.chunk_id, r.document_path, r.heading_path, r.content)
        for r in _search(conn, query, limit)
    ]


def search_with_score(
    conn: Connection,
    query: str,
    limit: int = 5,
) -> list[ScoredResult]:
    """Search chunks, returning the BM25 score alongside each result.

    Same contract as :func:`search`; use this when the score itself is
    needed, as the MCP server does when reporting results to the agent.

    Raises:
        StoreError: If the query cannot be executed.
    """
    return _search(conn, query, limit)


def list_documents(conn: Connection) -> list[DocumentInfo]:
    """List all indexed documents with chunk counts.

    Args:
        conn: An open database connection.

    Returns:
        A list of DocumentInfo (path, indexed_at, chunk_count), ordered
        by path.

    Raises:
        StoreError: If the documents cannot be listed.
    """
    try:
        cursor = conn.execute(
            """
            SELECT d.path, d.indexed_at, COUNT(c.chunk_id) AS chunk_count
            FROM documents d
            LEFT JOIN chunks c ON d.path = c.document_path
            GROUP BY d.path
            ORDER BY d.path
            """,
        )
    except sqlite3.Error as exc:
        raise StoreError("Failed to list indexed documents") from exc
    return [
        DocumentInfo(row[0], row[1], row[2])
        for row in cursor.fetchall()
    ]


def get_chunks(conn: Connection, path: str) -> list[str]:
    """Retrieve all content chunks for a document, in order.

    Args:
        conn: An open database connection.
        path: Document path as stored in the index.

    Returns:
        A list of content strings, in document order.

    Raises:
        StoreError: If the chunks cannot be retrieved.
    """
    try:
        cursor = conn.execute(
            """
            SELECT content FROM chunks
            WHERE document_path = ?
            ORDER BY CAST(chunk_index AS INTEGER)
            """,
            (path,),
        )
    except sqlite3.Error as exc:
        raise StoreError(f"Failed to retrieve chunks for {path!r}") from exc
    return [row[0] for row in cursor.fetchall()]