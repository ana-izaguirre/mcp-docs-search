"""SQLite FTS5 storage for document chunks."""

import sqlite3
from pathlib import Path
from typing import NamedTuple

MAX_CONTENT_LENGTH = 50000

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
            f"Run `mcp-docs-search index <folder>` first."
        )
    try:
        return sqlite3.connect(db_path)
    except sqlite3.Error as exc:
        raise StoreError(
            f"Database not found: {db_path}. "
            f"Run `mcp-docs-search index <folder>` first."
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
) -> None:
    """Insert a single chunk.

    Raises:
        ValueError: If content is empty or exceeds MAX_CONTENT_LENGTH.
        StoreError: If the chunk cannot be written to the index.
    """
    if not content or not content.strip():
        raise ValueError("Cannot insert empty content")

    if len(content) > MAX_CONTENT_LENGTH:
        raise ValueError(
            f"Content too long: {len(content)} characters > {MAX_CONTENT_LENGTH}"
        )

    try:
        conn.execute(
            """
            INSERT INTO chunks (chunk_id, document_path, heading_path, content)
            VALUES (?, ?, ?, ?)
            """,
            (chunk_id, document_path, heading_path, content),
        )
    except sqlite3.Error as exc:
        raise StoreError(f"Failed to insert chunk into {document_path}") from exc


def search(conn: Connection, query: str, limit: int = 5) -> list[SearchResult]:
    """Search chunks, ranked by BM25 relevance.

    Args:
        conn: An open database connection.
        query: FTS5 query string.
        limit: Maximum number of results, between 1 and 20.

    Returns:
        A list of (chunk_id, document_path, heading_path, content), most
        relevant first.

    Raises:
        ValueError: If query is empty or limit is out of range.
        StoreError: If the query cannot be executed.
    """
    if not query or not query.strip():
        raise ValueError("Query cannot be empty")

    if not 1 <= limit <= 20:
        raise ValueError(f"Limit must be between 1 and 20, got {limit}")

    try:
        cursor = conn.execute(
            """
            SELECT chunk_id, document_path, heading_path, content
            FROM chunks
            WHERE chunks MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, limit),
        )
    except sqlite3.Error as exc:
        raise StoreError(f"Search query failed: {query!r}") from exc
    return [(row[0], row[1], row[2], row[3]) for row in cursor.fetchall()]


def sanitise_query(query: str) -> str:
    """Sanitise a user query for safe FTS5 matching.

    Wraps each term in double quotes and escapes internal quotes so that
    special FTS5 characters (wildcards, parentheses, operators) are
    treated as literal text. This prevents ``sqlite3.OperationalError``
    on malformed FTS5 syntax.

    Args:
        query: Raw user query string.

    Returns:
        A sanitised query safe to pass to ``FTS5 MATCH``.
    """
    terms = query.split()
    escaped = ['"{}"'.format(term.replace('"', '""')) for term in terms]
    return " ".join(escaped)


def search_with_score(
    conn: Connection,
    query: str,
    limit: int = 5,
) -> list[ScoredResult]:
    """Search chunks with BM25 relevance score.

    Args:
        conn: An open database connection.
        query: FTS5 query string.
        limit: Maximum number of results, between 1 and 20.

    Returns:
        A list of ScoredResult (chunk_id, document_path, heading_path,
        content, score), most relevant first.

    Raises:
        ValueError: If query is empty or limit is out of range.
        StoreError: If the query cannot be executed.
    """
    if not query or not query.strip():
        raise ValueError("Query cannot be empty")

    if not 1 <= limit <= 20:
        raise ValueError(f"Limit must be between 1 and 20, got {limit}")

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
            (query, limit),
        )
    except sqlite3.Error as exc:
        raise StoreError(f"Search query failed: {query!r}") from exc
    return [
        ScoredResult(row[0], row[1], row[2], row[3], row[4])
        for row in cursor.fetchall()
    ]


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
        A list of content strings, ordered by chunk_id.

    Raises:
        StoreError: If the chunks cannot be retrieved.
    """
    try:
        cursor = conn.execute(
            """
            SELECT content FROM chunks
            WHERE document_path = ?
            ORDER BY chunk_id
            """,
            (path,),
        )
    except sqlite3.Error as exc:
        raise StoreError(f"Failed to retrieve chunks for {path!r}") from exc
    return [row[0] for row in cursor.fetchall()]