from pathlib import Path
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

def test_create_tables_creates_database(tmp_path: Path) -> None:
    """Test that create_tables creates the documents and chunks tables."""
    db_path = str(tmp_path / "test.db")

    conn = create_tables(db_path)
    try:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='documents'")
        assert cursor.fetchone() is not None

        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chunks'")
        assert cursor.fetchone() is not None
    finally:
        conn.close()


def test_create_tables_fails_on_existing_file(tmp_path: Path) -> None:
    """Test that create_tables fails when database file already exists."""
    db_path = str(tmp_path / "existing.db")
    (tmp_path / "existing.db").touch()

    with pytest.raises(StoreError) as exc_info:
        create_tables(db_path)

    assert "already exists" in str(exc_info.value).lower()


def test_insert_chunk(tmp_path: Path) -> None:
    """Test that insert_chunk properly inserts a chunk."""
    db_path = str(tmp_path / "test.db")
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


def test_insert_chunk_rejects_empty_content(tmp_path: Path) -> None:
    """Test that insert_chunk rejects empty content."""
    db_path = str(tmp_path / "test.db")
    conn = create_tables(db_path)
    try:
        with pytest.raises(ValueError) as exc_info:
            insert_chunk(conn, "chunk1", "doc1.md", "doc1.md > Section 1", "")

        assert "empty" in str(exc_info.value).lower()
    finally:
        conn.close()


def test_insert_chunk_rejects_too_long_content(tmp_path: Path) -> None:
    """Test that insert_chunk rejects content that's too long."""
    db_path = str(tmp_path / "test.db")
    conn = create_tables(db_path)
    try:
        long_content = "x" * 50001

        with pytest.raises(ValueError) as exc_info:
            insert_chunk(conn, "chunk1", "doc1.md", "doc1.md > Section 1", long_content)

        assert "too long" in str(exc_info.value).lower()
    finally:
        conn.close()


def test_insert_document_records_path_and_timestamp(tmp_path: Path) -> None:
    """Test that insert_document records a document row."""
    db_path = str(tmp_path / "test.db")
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


def test_insert_document_rejects_empty_path(tmp_path: Path) -> None:
    """Test that insert_document rejects an empty path."""
    db_path = str(tmp_path / "test.db")
    conn = create_tables(db_path)
    try:
        with pytest.raises(ValueError) as exc_info:
            insert_document(conn, "", "2025-01-15T10:30:00+00:00")
        assert "path" in str(exc_info.value).lower()
    finally:
        conn.close()


def test_search_with_valid_query(tmp_path: Path) -> None:
    """Test that search returns results for a valid query."""
    db_path = str(tmp_path / "test.db")
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


def test_search_empty_query(tmp_path: Path) -> None:
    """Test that search rejects empty query."""
    db_path = str(tmp_path / "test.db")
    conn = create_tables(db_path)
    try:
        with pytest.raises(ValueError) as exc_info:
            search(conn, "", 5)

        assert "empty" in str(exc_info.value).lower()
    finally:
        conn.close()


def test_search_invalid_limit(tmp_path: Path) -> None:
    """Test that search validates limit parameter."""
    db_path = str(tmp_path / "test.db")
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


def test_search_with_score_returns_scores(tmp_path: Path) -> None:
    """Test that search_with_score includes BM25 score."""
    db_path = str(tmp_path / "test.db")
    conn = create_tables(db_path)
    try:
        insert_chunk(conn, "c1", "doc.md", "doc.md > S", "content about testing")
        results = search_with_score(conn, "testing", 5)
        assert len(results) == 1
        assert results[0].chunk_id == "c1"
        assert isinstance(results[0].score, float)
    finally:
        conn.close()


def test_list_documents_returns_all_with_counts(tmp_path: Path) -> None:
    """Test that list_documents returns every document with chunk counts."""
    db_path = str(tmp_path / "test.db")
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


def test_get_chunks_ordered_by_chunk_id(tmp_path: Path) -> None:
    """Test that get_chunks returns content in chunk_id order."""
    db_path = str(tmp_path / "test.db")
    conn = create_tables(db_path)
    try:
        insert_chunk(conn, "0_1", "doc.md", "doc.md > Second", "second chunk")
        insert_chunk(conn, "0_0", "doc.md", "doc.md > First", "first chunk")
        conn.commit()

        chunks = get_chunks(conn, "doc.md")
        assert chunks == ["first chunk", "second chunk"]
    finally:
        conn.close()


def test_get_chunks_empty_for_unknown_path(tmp_path: Path) -> None:
    """Test that get_chunks returns empty list for unknown document."""
    db_path = str(tmp_path / "test.db")
    conn = create_tables(db_path)
    try:
        chunks = get_chunks(conn, "nonexistent.md")
        assert chunks == []
    finally:
        conn.close()


def test_open_connection_missing_raises_store_error() -> None:
    """Test that open_connection raises StoreError for missing DB."""
    with pytest.raises(StoreError):
        open_connection("/nonexistent/path/db.sqlite")


def test_store_error_wraps_sqlite3(tmp_path: Path) -> None:
    """Test that sqlite3 errors are wrapped in StoreError."""
    db_path = str(tmp_path / "test.db")
    conn = create_tables(db_path)
    conn.close()
    try:
        with pytest.raises(StoreError):
            search(conn, "test", 5)
    finally:
        if (tmp_path / "test.db").exists():
            (tmp_path / "test.db").unlink()


def test_sanitise_query_wraps_terms() -> None:
    """Test that sanitise_query wraps terms in quotes."""
    assert sanitise_query("hello world") == '"hello" "world"'


def test_sanitise_query_escapes_quotes() -> None:
    """Test that sanitise_query strips and escapes quotes."""
    assert sanitise_query('say "hi"') == '"say" "hi"'


def test_sanitise_query_empty() -> None:
    """Test that sanitise_query handles empty string."""
    assert sanitise_query("") == ""


def test_sanitise_query_strips_punctuation() -> None:
    """Test that sanitise_query strips FTS5 syntax characters."""
    assert sanitise_query(
        "I call an endpoint and it hangs forever, is there a timeout"
    ) == '"I" "call" "an" "endpoint" "and" "it" "hangs" "forever" "is" "there" "a" "timeout"'
    assert sanitise_query("what's the p95 latency?") == '"whats" "the" "p95" "latency"'
    assert sanitise_query("error: connection refused") == '"error" "connection" "refused"'
    assert sanitise_query("use --rebuild to recreate it") == '"use" "--rebuild" "to" "recreate" "it"'


def test_sanitise_query_only_punctuation() -> None:
    """Test that sanitise_query returns empty for punctuation-only input."""
    assert sanitise_query("!!! ???") == ""


def test_search_handles_punctuation_queries(tmp_path) -> None:
    """Test that search handles queries with punctuation without FTS5 errors."""
    db_path = str(tmp_path / "test.db")
    conn = create_tables(db_path)
    try:
        insert_chunk(
            conn, "0_0", "doc1.md", "doc1.md > S",
            "endpoint timeout configuration",
        )
        insert_chunk(
            conn, "0_1", "doc2.md", "doc2.md > S",
            "latency p95 metrics",
        )
        conn.commit()

        queries = [
            "I call an endpoint and it hangs forever, is there a timeout",
            "what's the p95 latency?",
            "error: connection refused",
            "use --rebuild to recreate it",
        ]
        for q in queries:
            results = search(conn, q, 5)
            assert isinstance(results, list)
    finally:
        conn.close()


def test_search_only_punctuation_returns_empty(tmp_path) -> None:
    """Test that a query of only punctuation returns an empty list."""
    db_path = str(tmp_path / "test.db")
    conn = create_tables(db_path)
    try:
        insert_chunk(conn, "0_0", "doc1.md", "doc1.md > S", "some content")
        conn.commit()

        results = search(conn, "!!! ???", 5)
        assert results == []
    finally:
        conn.close()


def test_search_falls_back_to_or(tmp_path: Path) -> None:
    """Test that search falls back to OR when AND finds no matches."""
    db_path = str(tmp_path / "test.db")
    conn = create_tables(db_path)
    try:
        insert_chunk(conn, "0_0", "doc1.md", "doc1.md > S", "alpha and beta")
        insert_chunk(conn, "0_1", "doc2.md", "doc2.md > S", "alpha and gamma")
        conn.commit()

        # No chunk contains both "beta" AND "gamma" — AND fails.
        results = search(conn, "beta gamma", 5)

        # OR fallback should find both chunks.
        assert len(results) == 2
        chunk_ids = {r[0] for r in results}
        assert chunk_ids == {"0_0", "0_1"}
    finally:
        conn.close()


def test_search_returns_and_results_no_fallback(tmp_path: Path) -> None:
    """Test that search returns AND results without OR fallback."""
    db_path = str(tmp_path / "test.db")
    conn = create_tables(db_path)
    try:
        insert_chunk(conn, "0_0", "doc1.md", "doc1.md > S", "alpha and beta")
        insert_chunk(conn, "0_1", "doc2.md", "doc2.md > S", "alpha and gamma")
        conn.commit()

        # Both terms appear together in chunk 0_0.
        results = search(conn, "beta alpha", 5)

        assert len(results) == 1
        assert results[0][0] == "0_0"
    finally:
        conn.close()


def test_search_with_score_falls_back_to_or(tmp_path: Path) -> None:
    """Test that search_with_score falls back to OR when AND finds nothing."""
    db_path = str(tmp_path / "test.db")
    conn = create_tables(db_path)
    try:
        insert_chunk(conn, "0_0", "doc1.md", "doc1.md > S", "alpha and beta")
        insert_chunk(conn, "0_1", "doc2.md", "doc2.md > S", "alpha and gamma")
        conn.commit()

        results = search_with_score(conn, "beta gamma", 5)

        assert len(results) == 2
        assert all(isinstance(r.score, float) for r in results)
    finally:
        conn.close()


def test_search_or_results_not_merged(tmp_path: Path) -> None:
    """Test that OR fallback returns only OR results, not a merge."""
    db_path = str(tmp_path / "test.db")
    conn = create_tables(db_path)
    try:
        # 0_0 has "beta" but not "gamma"
        # 0_1 has "gamma" but not "beta"
        insert_chunk(conn, "0_0", "doc1.md", "doc1.md > S", "alpha beta")
        insert_chunk(conn, "0_1", "doc2.md", "doc2.md > S", "gamma delta")
        conn.commit()

        results = search(conn, "beta gamma", 5)

        # AND empty (no chunk has both), OR finds both chunks.
        assert len(results) == 2
        chunk_ids = {r[0] for r in results}
        assert chunk_ids == {"0_0", "0_1"}
    finally:
        conn.close()
