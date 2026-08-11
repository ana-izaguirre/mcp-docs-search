import sqlite3
import tempfile
import pytest
from mcp_docs_search.store import (
    create_tables,
    get_chunks,
    insert_chunk,
    insert_document,
    list_documents,
    open_connection,
    sanitise_query,
    search,
    search_with_score,
    StoreError,
)

def test_create_tables_creates_database() -> None:
    """Test that create_tables creates the documents and chunks tables."""
    # Use a temp file that doesn't exist yet
    with tempfile.NamedTemporaryFile(suffix='.db', delete=True) as f:
        db_path = f.name
    
    conn = create_tables(db_path)
    
    try:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='documents'")
        assert cursor.fetchone() is not None
        
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chunks'")
        assert cursor.fetchone() is not None
        
    finally:
        conn.close()
        # Clean up
        import os
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_create_tables_fails_on_existing_file() -> None:
    """Test that create_tables fails when database file already exists."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    try:
        conn = sqlite3.connect(db_path)
        conn.close()
        
        with pytest.raises(StoreError) as exc_info:
            create_tables(db_path)

        assert "already exists" in str(exc_info.value).lower()
    finally:
        import os
        os.unlink(db_path)


def test_insert_chunk() -> None:
    """Test that insert_chunk properly inserts a chunk."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=True) as f:
        db_path = f.name
    
    conn = create_tables(db_path)
    
    try:
        insert_chunk(conn, "chunk1", "doc1.md", "doc1.md > Section 1", "Content of chunk 1")
        
        cursor = conn.execute("SELECT chunk_id, document_path, heading_path, content FROM chunks WHERE chunk_id = 'chunk1'")
        chunk = cursor.fetchone()
        
        assert chunk is not None
        assert chunk[0] == "chunk1"
        assert chunk[1] == "doc1.md"
        assert chunk[2] == "doc1.md > Section 1"
        assert chunk[3] == "Content of chunk 1"
    finally:
        conn.close()
        # Clean up
        import os
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_insert_chunk_rejects_empty_content() -> None:
    """Test that insert_chunk rejects empty content."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=True) as f:
        db_path = f.name
    
    conn = create_tables(db_path)
    
    try:
        with pytest.raises(ValueError) as exc_info:
            insert_chunk(conn, "chunk1", "doc1.md", "doc1.md > Section 1", "")
        
        assert "empty" in str(exc_info.value).lower()
    finally:
        conn.close()
        import os
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_insert_chunk_rejects_too_long_content() -> None:
    """Test that insert_chunk rejects content that's too long."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=True) as f:
        db_path = f.name
    
    conn = create_tables(db_path)
    
    try:
        long_content = "x" * 50001
        
        with pytest.raises(ValueError) as exc_info:
            insert_chunk(conn, "chunk1", "doc1.md", "doc1.md > Section 1", long_content)
        
        assert "too long" in str(exc_info.value).lower()
    finally:
        conn.close()
        import os
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_insert_document_records_path_and_timestamp() -> None:
    """Test that insert_document records a document row."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=True) as f:
        db_path = f.name

    conn = create_tables(db_path)

    try:
        insert_document(conn, "doc.md", "2025-01-15T10:30:00+00:00")
        conn.commit()

        cursor = conn.execute("SELECT path, indexed_at FROM documents")
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "doc.md"
        assert row[1] == "2025-01-15T10:30:00+00:00"
    finally:
        conn.close()
        import os
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_insert_document_rejects_empty_path() -> None:
    """Test that insert_document rejects an empty path."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=True) as f:
        db_path = f.name

    conn = create_tables(db_path)

    try:
        with pytest.raises(ValueError) as exc_info:
            insert_document(conn, "", "2025-01-15T10:30:00+00:00")
        assert "path" in str(exc_info.value).lower()
    finally:
        conn.close()
        import os
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_search_with_valid_query() -> None:
    """Test that search returns results for a valid query."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=True) as f:
        db_path = f.name
    
    conn = create_tables(db_path)
    
    try:
        insert_chunk(conn, "chunk1", "doc1.md", "doc1.md > Section 1", "Content about database and search")
        insert_chunk(conn, "chunk2", "doc2.md", "doc2.md > Section 2", "Another document about caching")
        
        results = search(conn, "database", 5)
        
        assert len(results) == 1
        assert results[0][0] == "chunk1"
        assert results[0][3] == "Content about database and search"
    finally:
        conn.close()
        import os
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_search_empty_query() -> None:
    """Test that search rejects empty query."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=True) as f:
        db_path = f.name
    
    conn = create_tables(db_path)
    
    try:
        with pytest.raises(ValueError) as exc_info:
            search(conn, "", 5)
        
        assert "empty" in str(exc_info.value).lower()
    finally:
        conn.close()
        import os
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_search_invalid_limit() -> None:
    """Test that search validates limit parameter."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=True) as f:
        db_path = f.name

    conn = create_tables(db_path)

    try:
        with pytest.raises(ValueError) as exc_info:
            search(conn, "test", 0)

        assert "between 1 and 20" in str(exc_info.value)

        with pytest.raises(ValueError) as exc_info:
            search(conn, "test", 21)

        assert "between 1 and 20" in str(exc_info.value)
    finally:
        conn.close()
        import os
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_search_with_score_returns_scores() -> None:
    """Test that search_with_score includes BM25 score."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=True) as f:
        db_path = f.name

    conn = create_tables(db_path)

    try:
        insert_chunk(conn, "c1", "doc.md", "doc.md > S", "content about testing")
        results = search_with_score(conn, "testing", 5)
        assert len(results) == 1
        assert results[0].chunk_id == "c1"
        assert isinstance(results[0].score, float)
    finally:
        conn.close()
        import os
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_list_documents_returns_all_with_counts() -> None:
    """Test that list_documents returns every document with chunk counts."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=True) as f:
        db_path = f.name

    conn = create_tables(db_path)

    try:
        conn.execute(
            "INSERT INTO documents (path, indexed_at) VALUES ('a.md', '2025-01-01')"
        )
        conn.execute(
            "INSERT INTO documents (path, indexed_at) VALUES ('b.md', '2025-01-02')"
        )
        insert_chunk(conn, "0_0", "a.md", "a.md > Intro", "hello world")
        conn.commit()

        docs = list_documents(conn)
        assert len(docs) == 2
        paths = {d.path for d in docs}
        assert paths == {"a.md", "b.md"}
        by_path = {d.path: d for d in docs}
        assert by_path["a.md"].chunk_count == 1
        assert by_path["b.md"].chunk_count == 0
    finally:
        conn.close()
        import os
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_get_chunks_ordered_by_chunk_id() -> None:
    """Test that get_chunks returns content in chunk_id order."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=True) as f:
        db_path = f.name

    conn = create_tables(db_path)

    try:
        insert_chunk(conn, "0_1", "doc.md", "doc.md > Second", "second chunk")
        insert_chunk(conn, "0_0", "doc.md", "doc.md > First", "first chunk")
        conn.commit()

        chunks = get_chunks(conn, "doc.md")
        assert chunks == ["first chunk", "second chunk"]
    finally:
        conn.close()
        import os
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_get_chunks_empty_for_unknown_path() -> None:
    """Test that get_chunks returns empty list for unknown document."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=True) as f:
        db_path = f.name

    conn = create_tables(db_path)

    try:
        chunks = get_chunks(conn, "nonexistent.md")
        assert chunks == []
    finally:
        conn.close()
        import os
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_open_connection_missing_raises_store_error() -> None:
    """Test that open_connection raises StoreError for missing DB."""
    with pytest.raises(StoreError):
        open_connection("/nonexistent/path/db.sqlite")


def test_store_error_wraps_sqlite3() -> None:
    """Test that sqlite3 errors are wrapped in StoreError."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=True) as f:
        db_path = f.name

    conn = create_tables(db_path)
    conn.close()

    try:
        with pytest.raises(StoreError):
            search(conn, "test", 5)
    finally:
        import os
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_sanitise_query_wraps_terms() -> None:
    """Test that sanitise_query wraps terms in quotes."""
    assert sanitise_query("hello world") == '"hello" "world"'


def test_sanitise_query_escapes_quotes() -> None:
    """Test that sanitise_query escapes internal quotes."""
    assert sanitise_query('say "hi"') == '"say" """hi"""'


def test_sanitise_query_empty() -> None:
    """Test that sanitise_query handles empty string."""
    assert sanitise_query("") == ""
