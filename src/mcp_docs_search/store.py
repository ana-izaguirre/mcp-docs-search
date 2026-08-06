def create_tables(db_path):
    """Create documents and chunks tables using SQLite FTS5.

    Args:
        db_path: Path to the SQLite database file

    Returns:
        sqlite3.Connection: Database connection
    """
    import sqlite3

    conn = sqlite3.connect(db_path)

    conn.execute("""
        CREATE VIRTUAL TABLE documents USING FTS5 (
            path TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNICODE61
        )
    """)

    conn.execute("""
        CREATE VIRTUAL TABLE chunks USING FTS5 (
            chunk_id TEXT,
            document_path TEXT NOT NULL,
            heading_path TEXT NOT NULL,
            content TEXT NOT NULL,
            score REAL,
            INDEX idx_chunks_document_path (document_path),
            UNICODE61
        )
    """)

    conn.commit()

    return conn


def insert_chunk(conn, chunk_id, document_path, heading_path, content):
    """Insert a chunk into the database.

    Args:
        conn: SQLite connection object
        chunk_id: Unique identifier for the chunk
        document_path: Path to the source document
        heading_path: Heading hierarchy path (e.g., "guia.md > Instalación > Configuración")
        content: Chunk text content

    Raises:
        ValueError: If content is empty or too long
    """
    if not content or not content.strip():
        raise ValueError("Cannot insert empty content")

    if len(content) > 50000:
        raise ValueError(f"Content too long: {len(content)} characters > 50000")

    conn.execute("""
        INSERT INTO chunks (chunk_id, document_path, heading_path, content, score)
        VALUES (?, ?, ?, ?, 0.0)
    """, (chunk_id, document_path, heading_path, content))


def search(conn, query, limit=5):
    """Search for chunks using FTS5 with BM25 ranking.

    Args:
        conn: SQLite connection object
        query: Search query string
        limit: Maximum number of results to return (1-20)

    Returns:
        List of tuples: (chunk_id, document_path, heading_path, content, score)

    Raises:
        ValueError: If query is empty or limit is out of range
    """
    if not query or not query.strip():
        raise ValueError("Query cannot be empty")

    if not 1 <= limit <= 20:
        raise ValueError(f"Limit must be between 1 and 20, got {limit}")

    cursor = conn.execute(
        "SELECT chunk_id, document_path, heading_path, content, score FROM chunks WHERE chunks MATCH ? ORDER BY score DESC LIMIT ?",
        (query, limit)
    )
    return cursor.fetchall()
