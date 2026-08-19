from pathlib import Path
import pytest
from mcp_docs_search.store import (
    MAX_CONTENT_LENGTH,
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
        insert_chunk(
            conn, "chunk1", "doc1.md", "doc1.md > Section 1", "Content of chunk 1", 0
        )

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
            insert_chunk(conn, "chunk1", "doc1.md", "doc1.md > Section 1", "", 0)

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
            insert_chunk(
                conn, "chunk1", "doc1.md", "doc1.md > Section 1", long_content, 0
            )

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
        insert_chunk(
            conn,
            "chunk1",
            "doc1.md",
            "doc1.md > Section 1",
            "Content about database and search",
            0,
        )
        insert_chunk(
            conn,
            "chunk2",
            "doc2.md",
            "doc2.md > Section 2",
            "Another document about caching",
            0,
        )

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
        insert_chunk(conn, "c1", "doc.md", "doc.md > S", "content about testing", 0)
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
        insert_chunk(conn, "0_0", "a.md", "a.md > Intro", "hello world", 0)
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
        insert_chunk(conn, "0_1", "doc.md", "doc.md > Second", "second chunk", 1)
        insert_chunk(conn, "0_0", "doc.md", "doc.md > First", "first chunk", 0)
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
    """Test that sanitise_query escapes internal quotes."""
    assert sanitise_query('say "hi"') == '"say" """hi"""'


def test_sanitise_query_empty() -> None:
    """Test that sanitise_query handles empty string."""
    assert sanitise_query("") == ""


def test_search_falls_back_to_or(tmp_path: Path) -> None:
    """Test that search falls back to OR when AND finds no matches."""
    db_path = str(tmp_path / "test.db")
    conn = create_tables(db_path)
    try:
        insert_chunk(conn, "0_0", "doc1.md", "doc1.md > S", "alpha and beta", 0)
        insert_chunk(conn, "0_1", "doc2.md", "doc2.md > S", "alpha and gamma", 0)
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
        insert_chunk(conn, "0_0", "doc1.md", "doc1.md > S", "alpha and beta", 0)
        insert_chunk(conn, "0_1", "doc2.md", "doc2.md > S", "alpha and gamma", 0)
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
        insert_chunk(conn, "0_0", "doc1.md", "doc1.md > S", "alpha and beta", 0)
        insert_chunk(conn, "0_1", "doc2.md", "doc2.md > S", "alpha and gamma", 0)
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
        insert_chunk(conn, "0_0", "doc1.md", "doc1.md > S", "alpha beta", 0)
        insert_chunk(conn, "0_1", "doc2.md", "doc2.md > S", "gamma delta", 0)
        conn.commit()

        results = search(conn, "beta gamma", 5)

        # AND empty (no chunk has both), OR finds both chunks.
        assert len(results) == 2
        chunk_ids = {r[0] for r in results}
        assert chunk_ids == {"0_0", "0_1"}
    finally:
        conn.close()


# --- chunk ordering -----------------------------------------------------------

def test_get_chunks_orders_beyond_ten_chunks(tmp_path: Path) -> None:
    """Regression: ordering must be numeric, not lexicographic.

    chunk_id is TEXT of the form "<file>_<chunk>", so ordering by it put
    "0_10" between "0_1" and "0_2" and scrambled every document with more
    than ten chunks.
    """
    db_path = str(tmp_path / "test.db")
    conn = create_tables(db_path)
    try:
        for i in range(12):
            insert_chunk(
                conn, f"0_{i}", "doc.md", f"doc.md > S{i}", f"body {i}", i
            )
        conn.commit()

        assert get_chunks(conn, "doc.md") == [f"body {i}" for i in range(12)]
    finally:
        conn.close()


def test_get_chunks_ignores_insertion_order(tmp_path: Path) -> None:
    """chunk_index decides the order, not the order rows were written."""
    db_path = str(tmp_path / "test.db")
    conn = create_tables(db_path)
    try:
        insert_chunk(conn, "c", "doc.md", "doc.md > C", "third", 2)
        insert_chunk(conn, "a", "doc.md", "doc.md > A", "first", 0)
        insert_chunk(conn, "b", "doc.md", "doc.md > B", "second", 1)
        conn.commit()

        assert get_chunks(conn, "doc.md") == ["first", "second", "third"]
    finally:
        conn.close()


def test_get_chunks_only_returns_the_requested_document(tmp_path: Path) -> None:
    db_path = str(tmp_path / "test.db")
    conn = create_tables(db_path)
    try:
        insert_chunk(conn, "0_0", "a.md", "a.md > S", "from a", 0)
        insert_chunk(conn, "1_0", "b.md", "b.md > S", "from b", 0)
        conn.commit()

        assert get_chunks(conn, "a.md") == ["from a"]
    finally:
        conn.close()


def test_insert_chunk_rejects_negative_index(tmp_path: Path) -> None:
    db_path = str(tmp_path / "test.db")
    conn = create_tables(db_path)
    try:
        with pytest.raises(ValueError, match="chunk_index"):
            insert_chunk(conn, "c", "doc.md", "doc.md > S", "body", -1)
    finally:
        conn.close()


# --- validation boundaries ----------------------------------------------------

def test_insert_chunk_accepts_content_at_max_length(tmp_path: Path) -> None:
    """The limit is inclusive: exactly MAX_CONTENT_LENGTH is allowed."""
    db_path = str(tmp_path / "test.db")
    conn = create_tables(db_path)
    try:
        insert_chunk(
            conn, "c", "doc.md", "doc.md > S", "x" * MAX_CONTENT_LENGTH, 0
        )
        conn.commit()
        assert len(get_chunks(conn, "doc.md")) == 1
    finally:
        conn.close()


def test_insert_chunk_rejects_one_over_max_length(tmp_path: Path) -> None:
    db_path = str(tmp_path / "test.db")
    conn = create_tables(db_path)
    try:
        with pytest.raises(ValueError, match="too long"):
            insert_chunk(
                conn,
                "c",
                "doc.md",
                "doc.md > S",
                "x" * (MAX_CONTENT_LENGTH + 1),
                0,
            )
    finally:
        conn.close()


def test_insert_chunk_rejects_whitespace_only_content(tmp_path: Path) -> None:
    db_path = str(tmp_path / "test.db")
    conn = create_tables(db_path)
    try:
        with pytest.raises(ValueError, match="empty"):
            insert_chunk(conn, "c", "doc.md", "doc.md > S", "   \n\t ", 0)
    finally:
        conn.close()


def test_insert_document_rejects_empty_indexed_at(tmp_path: Path) -> None:
    db_path = str(tmp_path / "test.db")
    conn = create_tables(db_path)
    try:
        with pytest.raises(ValueError, match="indexed_at"):
            insert_document(conn, "doc.md", "")
    finally:
        conn.close()


def test_insert_document_duplicate_path_raises_store_error(
    tmp_path: Path,
) -> None:
    """path is the primary key; a repeat must surface as StoreError."""
    db_path = str(tmp_path / "test.db")
    conn = create_tables(db_path)
    try:
        insert_document(conn, "doc.md", "2025-01-01")
        with pytest.raises(StoreError):
            insert_document(conn, "doc.md", "2025-01-02")
    finally:
        conn.close()


@pytest.mark.parametrize("limit", [1, 20])
def test_search_accepts_limit_boundaries(tmp_path: Path, limit: int) -> None:
    db_path = str(tmp_path / "test.db")
    conn = create_tables(db_path)
    try:
        insert_chunk(conn, "c", "doc.md", "doc.md > S", "alpha content", 0)
        conn.commit()
        assert isinstance(search(conn, "alpha", limit), list)
    finally:
        conn.close()


@pytest.mark.parametrize("limit", [0, 21, -1])
def test_search_rejects_limit_outside_boundaries(
    tmp_path: Path, limit: int
) -> None:
    db_path = str(tmp_path / "test.db")
    conn = create_tables(db_path)
    try:
        with pytest.raises(ValueError, match="between 1 and 20"):
            search(conn, "alpha", limit)
    finally:
        conn.close()


def test_search_rejects_whitespace_only_query(tmp_path: Path) -> None:
    db_path = str(tmp_path / "test.db")
    conn = create_tables(db_path)
    try:
        with pytest.raises(ValueError, match="empty"):
            search(conn, "   ", 5)
    finally:
        conn.close()


@pytest.mark.parametrize(
    "raw",
    ['NEAR(alpha beta)', 'alpha*', '"unbalanced', 'alpha OR', '(((', 'a AND'],
)
def test_sanitised_operators_never_raise(tmp_path: Path, raw: str) -> None:
    """SPEC: operator characters are literal terms, never FTS5 syntax."""
    db_path = str(tmp_path / "test.db")
    conn = create_tables(db_path)
    try:
        insert_chunk(conn, "c", "doc.md", "doc.md > S", "alpha and beta", 0)
        conn.commit()
        assert isinstance(search(conn, sanitise_query(raw), 5), list)
    finally:
        conn.close()


def test_list_documents_on_empty_index(tmp_path: Path) -> None:
    db_path = str(tmp_path / "test.db")
    conn = create_tables(db_path)
    try:
        assert list_documents(conn) == []
    finally:
        conn.close()


def test_search_on_empty_index_returns_no_results(tmp_path: Path) -> None:
    db_path = str(tmp_path / "test.db")
    conn = create_tables(db_path)
    try:
        assert search(conn, sanitise_query("anything"), 5) == []
    finally:
        conn.close()


def test_search_with_score_rejects_bad_limit(tmp_path: Path) -> None:
    db_path = str(tmp_path / "test.db")
    conn = create_tables(db_path)
    try:
        with pytest.raises(ValueError, match="between 1 and 20"):
            search_with_score(conn, "alpha", 99)
    finally:
        conn.close()


def test_search_respects_limit(tmp_path: Path) -> None:
    db_path = str(tmp_path / "test.db")
    conn = create_tables(db_path)
    try:
        for i in range(10):
            insert_chunk(
                conn, f"c{i}", "doc.md", f"doc.md > S{i}", "alpha content", i
            )
        conn.commit()
        assert len(search(conn, "alpha", 3)) == 3
    finally:
        conn.close()
