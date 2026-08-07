import sqlite3
import tempfile
import pytest
from mcp_docs_search.store import create_tables, insert_chunk, search

def test_create_tables_creates_database():
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


def test_create_tables_fails_on_existing_file():
    """Test that create_tables fails when database file already exists."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    try:
        conn = sqlite3.connect(db_path)
        conn.close()
        
        with pytest.raises(sqlite3.OperationalError) as exc_info:
            create_tables(db_path)
        
        assert "already exists" in str(exc_info.value).lower()
    finally:
        import os
        os.unlink(db_path)


def test_insert_chunk():
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


def test_insert_chunk_rejects_empty_content():
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


def test_insert_chunk_rejects_too_long_content():
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


def test_search_with_valid_query():
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


def test_search_empty_query():
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


def test_search_invalid_limit():
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
