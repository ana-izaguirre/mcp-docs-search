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
from mcp_docs_search.store import (
    create_tables,
    insert_chunk,
    open_connection,
    sanitise_query,
)

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
        "This guide covers installation and basic setup of the package.", 0
    )
    insert_chunk(
        conn, "0_1", "guide.md", "guide.md > Configuration",
        "Configure retries and timeouts in the config file.", 1
    )
    insert_chunk(
        conn, "1_0", "reference.md", "reference.md > API",
        "The API listens on port 8080 and supports HTTP and gRPC.", 0
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


# --- FTS5 query sanitiser -----------------------------------------------


def test_sanitise_query_wraps_terms_in_quotes() -> None:
    assert sanitise_query("hello world") == '"hello" "world"'


def test_sanitise_query_escapes_internal_quotes() -> None:
    assert sanitise_query('say "hi"') == '"say" """hi"""'


def test_sanitise_query_handles_special_operators() -> None:
    result = sanitise_query("port* NEAR(foo) AND bar")
    assert isinstance(result, str)
    assert '"' in result


def test_sanitise_query_empty_string() -> None:
    assert sanitise_query("") == ""


def test_sanitise_query_whitespace_only() -> None:
    assert sanitise_query("   ") == ""


def test_sanitise_query_single_term() -> None:
    assert sanitise_query("retries") == '"retries"'


# --- server construction and tool registration --------------------------------

@pytest.mark.anyio
async def test_create_server_registers_the_three_tools(db_path: Path) -> None:
    """The success path of create_server was previously untested.

    Only the missing-database branch had coverage, so a broken decorator
    or a renamed tool would have reached manual testing.
    """
    server = create_server(db_path)
    tools = await server.list_tools()
    assert {t.name for t in tools} == {
        "search_docs",
        "list_sources",
        "get_document",
    }


@pytest.mark.anyio
async def test_registered_tools_declare_their_inputs(db_path: Path) -> None:
    server = create_server(db_path)
    schemas = {t.name: t.input_schema for t in await server.list_tools()}

    assert schemas["search_docs"]["required"] == ["query"]
    assert "limit" in schemas["search_docs"]["properties"]
    assert schemas["get_document"]["required"] == ["path"]
    assert schemas["list_sources"]["properties"] == {}


@pytest.mark.anyio
async def test_every_tool_has_a_description(db_path: Path) -> None:
    """The description is what the agent uses to choose a tool."""
    server = create_server(db_path)
    for tool in await server.list_tools():
        assert tool.description
        assert len(tool.description.strip()) > 40


# --- limit clamping, exhaustively ---------------------------------------------

@pytest.mark.parametrize(
    ("given", "expected"),
    [(None, 5), (-10, 1), (0, 1), (1, 1), (5, 5), (20, 20), (21, 20), (999, 20)],
)
def test_clamp_limit_boundaries(given: int | None, expected: int) -> None:
    assert _clamp_limit(given) == expected


# --- get_document edge cases --------------------------------------------------

@pytest.mark.anyio
async def test_get_document_empty_path_is_actionable(db_path: Path) -> None:
    result = await _get_document("")
    assert "required" in result.lower()
    assert "list_sources" in result


@pytest.mark.anyio
async def test_get_document_whitespace_path_is_actionable(
    db_path: Path,
) -> None:
    result = await _get_document("   ")
    assert "list_sources" in result


@pytest.mark.anyio
async def test_get_document_returns_chunks_in_document_order(
    tmp_path: Path,
) -> None:
    """Regression for lexicographic chunk ordering, at the server boundary."""
    path = tmp_path / "ordered.db"
    conn = create_tables(str(path))
    conn.execute(
        "INSERT INTO documents (path, indexed_at) VALUES ('long.md', '2025-01-01')"
    )
    for i in range(12):
        insert_chunk(conn, f"0_{i}", "long.md", f"long.md > S{i}", f"body {i}", i)
    conn.commit()
    conn.close()

    server_mod._conn = open_connection(str(path))
    result = await _get_document("long.md")

    assert result == "\n\n".join(f"body {i}" for i in range(12))


# --- store failures degrade into actionable answers, never tracebacks ---------

def _close_connection() -> None:
    """Drop the live connection so store calls raise StoreError."""
    assert server_mod._conn is not None
    server_mod._conn.close()


@pytest.mark.anyio
async def test_search_docs_survives_a_store_failure(db_path: Path) -> None:
    _close_connection()
    assert await _search_docs("retries", 5) == []


@pytest.mark.anyio
async def test_list_sources_survives_a_store_failure(db_path: Path) -> None:
    _close_connection()
    assert await _list_sources() == []


@pytest.mark.anyio
async def test_get_document_survives_a_store_failure(db_path: Path) -> None:
    _close_connection()
    result = await _get_document("guide.md")
    assert "unavailable" in result.lower()
    assert "list_sources" in result


def test_uninitialised_connection_raises_runtime_error() -> None:
    server_mod._conn = None
    with pytest.raises(RuntimeError, match="not initialized"):
        server_mod._get_conn()


# --- stdout stays clean on failure paths too ----------------------------------

def test_nothing_writes_to_stdout_on_failure_paths(
    db_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """stdout is the MCP protocol channel; error handling must not touch it."""
    _close_connection()
    asyncio.run(_search_docs("retries", 5))
    asyncio.run(_list_sources())
    asyncio.run(_get_document("guide.md"))
    asyncio.run(_get_document("missing.md"))
    assert capsys.readouterr().out == ""
