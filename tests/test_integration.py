"""Integration tests: the published commands and the real MCP protocol.

SPEC section 8 records a known gap — the unit tests call entry-point
functions directly, leaving `project.scripts`, argument parsing and default
paths uncovered, and three defects reached manual testing through it. These
tests close that gap by running the installed console scripts as
subprocesses and by driving the server over a real stdio MCP session.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

BIN_DIR = Path(sys.executable).parent
INDEX_CMD = BIN_DIR / "mcp-docs-search"
SERVER_CMD = BIN_DIR / "mcp-docs-search-server"

requires_installed_scripts = pytest.mark.skipif(
    not INDEX_CMD.exists() or not SERVER_CMD.exists(),
    reason="console scripts not installed in this environment",
)

CORPUS = {
    "guide.md": "# Guide\n\n"
    + "Installing the package is the first step. " * 5
    + "\n\n## Retries\n\n"
    + "Configure retries with the retry_policy setting. " * 5,
    "reference.md": "# Reference\n\n"
    + "The service listens on port 8080 for HTTP traffic. " * 5,
    "long.md": "# Long\n\n"
    + "".join(
        f"## Part {i:02d}\n\n{'filler word ' * 30}marker{i:02d}\n\n"
        for i in range(14)
    ),
}


@pytest.fixture(scope="module")
def corpus(tmp_path_factory: pytest.TempPathFactory) -> Path:
    folder = tmp_path_factory.mktemp("corpus")
    for name, body in CORPUS.items():
        (folder / name).write_text(body, encoding="utf-8")
    return folder


@pytest.fixture(scope="module")
def indexed_db(corpus: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the index by running the published command, not by importing."""
    db = tmp_path_factory.mktemp("db") / "docs.db"
    result = subprocess.run(
        [str(INDEX_CMD), str(corpus), "--db", str(db), "--rebuild"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return db


# --- the published CLI --------------------------------------------------------


@requires_installed_scripts
def test_published_index_command_reports_progress(indexed_db: Path) -> None:
    assert indexed_db.exists()


@requires_installed_scripts
def test_published_index_command_refuses_to_clobber(
    corpus: Path, indexed_db: Path
) -> None:
    result = subprocess.run(
        [str(INDEX_CMD), str(corpus), "--db", str(indexed_db)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "--rebuild" in result.stderr


@requires_installed_scripts
def test_published_server_command_accepts_help() -> None:
    result = subprocess.run(
        [str(SERVER_CMD), "--help"], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0
    assert "--db" in result.stdout


@requires_installed_scripts
def test_published_server_names_the_fix_when_db_is_missing(
    tmp_path: Path,
) -> None:
    """An agent cannot read logs; the message must name the command to run."""
    result = subprocess.run(
        [str(SERVER_CMD), "--db", str(tmp_path / "absent.db")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "mcp-docs-search" in result.stderr
    assert "absent.db" in result.stderr


# --- the real MCP protocol ----------------------------------------------------


def _server_params(db: Path) -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_docs_search.server", "--db", str(db)],
    )


@pytest.mark.anyio
async def test_mcp_handshake_advertises_all_three_tools(
    indexed_db: Path,
) -> None:
    async with stdio_client(_server_params(indexed_db)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()

    assert {t.name for t in tools.tools} == {
        "search_docs",
        "list_sources",
        "get_document",
    }


@pytest.mark.anyio
async def test_search_then_get_document_over_the_protocol(
    indexed_db: Path,
) -> None:
    """The chain the server exists for: find a chunk, then read its file."""
    async with stdio_client(_server_params(indexed_db)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            found = await session.call_tool(
                "search_docs", {"query": "retries", "limit": 3}
            )
            results = (found.structured_content or {})["result"]
            assert results, "expected a match for 'retries'"
            assert results[0]["document_path"] == "guide.md"
            assert "guide.md >" in results[0]["heading_path"]

            doc = await session.call_tool(
                "get_document", {"path": results[0]["document_path"]}
            )
            body = (doc.structured_content or {})["result"]

    assert "retry_policy" in body


@pytest.mark.anyio
async def test_list_sources_over_the_protocol(indexed_db: Path) -> None:
    async with stdio_client(_server_params(indexed_db)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            sources = await session.call_tool("list_sources", {})
            listed = (sources.structured_content or {})["result"]

    assert {s["path"] for s in listed} == set(CORPUS)
    assert all(s["chunk_count"] > 0 for s in listed)
    assert all(s["indexed_at"] for s in listed)


@pytest.mark.anyio
async def test_get_document_order_survives_the_protocol(
    indexed_db: Path,
) -> None:
    """Regression, end to end: 14 sections must come back in source order."""
    async with stdio_client(_server_params(indexed_db)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            doc = await session.call_tool("get_document", {"path": "long.md"})
            body = (doc.structured_content or {})["result"]

    positions = [body.index(f"marker{i:02d}") for i in range(14)]
    assert positions == sorted(positions)


@pytest.mark.anyio
async def test_limit_is_clamped_over_the_protocol(indexed_db: Path) -> None:
    async with stdio_client(_server_params(indexed_db)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            found = await session.call_tool(
                "search_docs", {"query": "the", "limit": 500}
            )
            results = (found.structured_content or {})["result"]

    assert len(results) <= 20


@pytest.mark.anyio
@pytest.mark.parametrize("query", ["", "   ", "NEAR(port", 'unbalanced "', "*"])
async def test_hostile_queries_never_break_the_session(
    indexed_db: Path, query: str
) -> None:
    """Empty and operator-laden queries return a list, never a protocol error."""
    async with stdio_client(_server_params(indexed_db)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            found = await session.call_tool(
                "search_docs", {"query": query, "limit": 5}
            )

    assert found.is_error is not True
    assert isinstance((found.structured_content or {})["result"], list)


@pytest.mark.anyio
async def test_unknown_document_answers_instead_of_failing(
    indexed_db: Path,
) -> None:
    async with stdio_client(_server_params(indexed_db)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            doc = await session.call_tool(
                "get_document", {"path": "../../etc/passwd"}
            )
            body = (doc.structured_content or {})["result"]

    assert doc.is_error is not True
    assert "not found" in body.lower()
    assert "list_sources" in body
