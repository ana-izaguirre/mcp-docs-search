"""SQLite FTS5 storage for document chunks."""

import sqlite3
from pathlib import Path

MAX_CONTENT_LENGTH = 50000

SearchResult = tuple[str, str, str, str]


def create_tables(db_path: str) -> sqlite3.Connection:
    """Create the documents and chunks tables.

    Args:
        db_path: Path to the SQLite database file. Must not already exist.

    Returns:
        An open connection to the new database.

    Raises:
        sqlite3.OperationalError: If the database file already exists.
    """
    if Path(db_path).exists():
        raise sqlite3.OperationalError(
            f"Database already exists: {db_path}. Use --rebuild to recreate it."
        )

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
    return conn


def open_connection(db_path: str) -> sqlite3.Connection:
    """Open an existing database.

    Raises:
        sqlite3.OperationalError: If the database file does not exist.
    """
    if not Path(db_path).exists():
        raise sqlite3.OperationalError(
            f"Database not found: {db_path}. Run `mcp-docs-search index <folder>` first."
        )
    return sqlite3.connect(db_path)


def insert_chunk(
    conn: sqlite3.Connection,
    chunk_id: str,
    document_path: str,
    heading_path: str,
    content: str,
) -> None:
    """Insert a single chunk.

    Raises:
        ValueError: If content is empty or exceeds MAX_CONTENT_LENGTH.
    """
    if not content or not content.strip():
        raise ValueError("Cannot insert empty content")

    if len(content) > MAX_CONTENT_LENGTH:
        raise ValueError(
            f"Content too long: {len(content)} characters > {MAX_CONTENT_LENGTH}"
        )

    conn.execute(
        """
        INSERT INTO chunks (chunk_id, document_path, heading_path, content)
        VALUES (?, ?, ?, ?)
        """,
        (chunk_id, document_path, heading_path, content),
    )


def search(conn: sqlite3.Connection, query: str, limit: int = 5) -> list[SearchResult]:
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
    """
    if not query or not query.strip():
        raise ValueError("Query cannot be empty")

    if not 1 <= limit <= 20:
        raise ValueError(f"Limit must be between 1 and 20, got {limit}")

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
    return [(row[0], row[1], row[2], row[3]) for row in cursor.fetchall()]