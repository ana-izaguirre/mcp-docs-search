"""Tests for MCP server tool handlers."""

import asyncio
from pathlib import Path

import pytest

from mcp_docs_search.server import (
    _clamp_limit,
    _get_document,
    _list_sources,
    _search_docs,
    create_server,
)
from mcp_docs_search.store import create_tables, insert_chunk, open_connection

import mcp_docs_search.server as server_mod


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Create a small indexed database for testing."""
    path = tmp_path / "test.db"
    conn = create_tables(str(path))
    conn.execute(
        "INSERT INTO documents (path, indexed_at) VALUES ('guide.md', '2025-01-15')"
    )
    conn.execute(
        "INSERT INTO documents (path, indexed_at) VALUES ('reference.md', '2025-01-16')"
    )
    insert_chunk(
        conn, "0_0", "guide.md", "guide.md > Introduction",
        "This guide covers installation and basic setup of the package."
    )
    insert_chunk(
        conn, "0_1", "guide.md", "guide.md > Configuration",
        "Configure retries and timeouts in the config file."
    )
    insert_chunk(
        conn, "1_0", "reference.md", "reference.md > API",
        "The API listens on port 8080 and supports HTTP and gRPC."
    )
    conn.commit()
    conn.close()

    server_mod._conn = open_connection(str(path))
    return path


@pytest.mark.anyio
async def test_search_docs_returns_shape(db_path: Path) -> None:
    results = await _search_docs("retries", 5)
    assert isinstance(results, list)
    assert len(results) >= 1
    item = results[0]
    assert "chunk_id" in item
    assert "document_path" in item
    assert "heading_path" in item
    assert "content" in item
    assert "score" in item
    assert isinstance(item["score"], float)


@pytest.mark.anyio
async def test_search_docs_ranking(db_path: Path) -> None:
    results = await _search_docs("retries", 5)
    assert results[0]["document_path"] == "guide.md"
    assert "retries" in results[0]["content"]


@pytest.mark.anyio
async def test_list_sources_returns_shape(db_path: Path) -> None:
    results = await _list_sources()
    assert isinstance(results, list)
    assert len(results) == 2
    item = results[0]
    assert "path" in item
    assert "indexed_at" in item
    assert "chunk_count" in item
    assert item["path"] in ("guide.md", "reference.md")


@pytest.mark.anyio
async def test_get_document_returns_full_content(db_path: Path) -> None:
    result = await _get_document("guide.md")
    assert isinstance(result, str)
    assert "installation" in result
    assert "Configure" in result


@pytest.mark.anyio
async def test_get_document_missing_returns_actionable(db_path: Path) -> None:
    result = await _get_document("nonexistent.md")
    assert isinstance(result, str)
    assert "not found" in result.lower()
    assert "list_sources" in result


@pytest.mark.anyio
async def test_limit_clamped_below_min(db_path: Path) -> None:
    results = await _search_docs("the", 0)
    assert isinstance(results, list)
    assert len(results) <= 1


@pytest.mark.anyio
async def test_limit_clamped_above_max(db_path: Path) -> None:
    results = await _search_docs("the", 100)
    assert isinstance(results, list)
    assert len(results) <= 20


@pytest.mark.anyio
async def test_empty_query_returns_empty_list(db_path: Path) -> None:
    results = await _search_docs("", 5)
    assert results == []


@pytest.mark.anyio
async def test_whitespace_query_returns_empty_list(db_path: Path) -> None:
    results = await _search_docs("   ", 5)
    assert results == []


@pytest.mark.anyio
async def test_fts5_special_chars_do_not_raise(db_path: Path) -> None:
    results = await _search_docs("port*", 5)
    assert isinstance(results, list)

    results = await _search_docs('http "and"', 5)
    assert isinstance(results, list)

    results = await _search_docs("NEAR(port)", 5)
    assert isinstance(results, list)


def test_nothing_writes_to_stdout(db_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    asyncio.run(_search_docs("retries", 5))
    asyncio.run(_list_sources())
    asyncio.run(_get_document("guide.md"))
    captured = capsys.readouterr()
    assert captured.out == ""


def test_create_server_missing_db_exits(tmp_path: Path) -> None:
    missing = tmp_path / "nope.db"
    with pytest.raises(SystemExit) as exc_info:
        create_server(missing)
    assert exc_info.value.code == 1


def test_create_server_missing_db_stderr(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "nope.db"
    with pytest.raises(SystemExit):
        create_server(missing)
    captured = capsys.readouterr()
    assert "index" in captured.err.lower() or "not found" in captured.err.lower()


def test_clamp_limit_default() -> None:
    assert _clamp_limit(None) == 5
    assert _clamp_limit(0) == 1
    assert _clamp_limit(-5) == 1
    assert _clamp_limit(1) == 1
    assert _clamp_limit(20) == 20
    assert _clamp_limit(21) == 20
    assert _clamp_limit(100) == 20
    assert _clamp_limit(5) == 5
