"""Tests for the indexing CLI."""

from pathlib import Path

import pytest

import mcp_docs_search.cli as cli_module
from mcp_docs_search.cli import main
from mcp_docs_search.store import (
    StoreError,
    get_chunks,
    list_documents,
    open_connection,
)


def test_small_corpus_indexes_successfully(tmp_path: Path) -> None:
    """A small corpus indexes successfully and reports correct counts."""
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "guide.md").write_text(
        "# Setup\n\nShort.\n\n## Config\n\n" + "x" * 200 + "\n",
        encoding="utf-8",
    )
    db = tmp_path / "docs.db"

    rc = main([str(folder), "--db", str(db)])

    assert rc == 0
    assert db.exists()
    conn = open_connection(str(db))
    cursor = conn.execute("SELECT COUNT(*) FROM chunks")
    count = cursor.fetchone()[0]
    conn.close()
    assert count == 1


def test_empty_folder_exits_1_and_creates_no_db(tmp_path: Path) -> None:
    """Empty folder exits 1 and creates no database file."""
    folder = tmp_path / "empty"
    folder.mkdir()
    db = tmp_path / "docs.db"

    rc = main([str(folder), "--db", str(db)])

    assert rc == 1
    assert not db.exists()


def test_folder_without_md_files_exits_1(tmp_path: Path) -> None:
    """A folder with no .md files exits 1 and creates no database."""
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "notes.txt").write_text("Not markdown.\n", encoding="utf-8")
    db = tmp_path / "docs.db"

    rc = main([str(folder), "--db", str(db)])

    assert rc == 1
    assert not db.exists()


def test_existing_db_without_rebuild_exits_1(tmp_path: Path) -> None:
    """Existing .db without --rebuild exits 1."""
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "a.md").write_text("# Title\n\nContent.\n", encoding="utf-8")
    db = tmp_path / "docs.db"
    db.write_text("existing", encoding="utf-8")

    rc = main([str(folder), "--db", str(db)])

    assert rc == 1


def test_existing_db_with_rebuild_is_replaced(tmp_path: Path) -> None:
    """Existing .db with --rebuild is replaced."""
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "a.md").write_text("# Title\n\nContent.\n", encoding="utf-8")
    db = tmp_path / "docs.db"
    db.write_text("existing content", encoding="utf-8")

    rc = main([str(folder), "--db", str(db), "--rebuild"])

    assert rc == 0
    assert db.exists()
    conn = open_connection(str(db))
    cursor = conn.execute("SELECT COUNT(*) FROM chunks")
    count = cursor.fetchone()[0]
    conn.close()
    assert count == 1


def test_undecodable_file_is_skipped(tmp_path: Path) -> None:
    """An undecodable file is skipped, run still exits 0."""
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "good.md").write_text("# Good\n\nContent.\n", encoding="utf-8")
    (folder / "bad.md").write_bytes(b"\xff\xfe\x00\x00Not valid UTF-8")
    db = tmp_path / "docs.db"

    rc = main([str(folder), "--db", str(db)])

    assert rc == 0
    assert db.exists()
    conn = open_connection(str(db))
    cursor = conn.execute("SELECT COUNT(*) FROM chunks")
    count = cursor.fetchone()[0]
    conn.close()
    assert count == 1


def test_stored_paths_use_forward_slashes(tmp_path: Path) -> None:
    """Stored paths use forward slashes even for nested folders."""
    folder = tmp_path / "docs"
    sub = folder / "sub" / "deep"
    sub.mkdir(parents=True)
    (sub / "nested.md").write_text("# Nested\n\nContent.\n", encoding="utf-8")
    db = tmp_path / "docs.db"

    rc = main([str(folder), "--db", str(db)])

    assert rc == 0
    conn = open_connection(str(db))
    cursor = conn.execute("SELECT document_path FROM chunks")
    paths = [row[0] for row in cursor.fetchall()]
    conn.close()
    assert paths == ["sub/deep/nested.md"]


def test_documents_table_has_one_row_per_file(tmp_path: Path) -> None:
    """After indexing, documents has one row per indexed file."""
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "a.md").write_text("# A\n\nContent A.\n", encoding="utf-8")
    (folder / "b.md").write_text("# B\n\nContent B.\n", encoding="utf-8")
    db = tmp_path / "docs.db"

    rc = main([str(folder), "--db", str(db)])

    assert rc == 0
    conn = open_connection(str(db))
    cursor = conn.execute("SELECT COUNT(*) FROM documents")
    count = cursor.fetchone()[0]
    conn.close()
    assert count == 2


def test_skipped_file_produces_no_document_row(tmp_path: Path) -> None:
    """A file that fails to read is skipped and produces no documents row."""
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "good.md").write_text("# Good\n\nContent.\n", encoding="utf-8")
    (folder / "bad.md").write_bytes(b"\xff\xfe\x00\x00Not valid UTF-8")
    db = tmp_path / "docs.db"

    rc = main([str(folder), "--db", str(db)])

    assert rc == 0
    conn = open_connection(str(db))
    cursor = conn.execute("SELECT COUNT(*) FROM documents")
    count = cursor.fetchone()[0]
    conn.close()
    assert count == 1


def test_list_documents_chunk_count_matches(tmp_path: Path) -> None:
    """list_documents chunk_count matches the actual number of chunks."""
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "multi.md").write_text(
        "# First\n\n" + "x" * 200 + "\n\n## Second\n\n" + "y" * 200 + "\n",
        encoding="utf-8",
    )
    db = tmp_path / "docs.db"

    rc = main([str(folder), "--db", str(db)])

    assert rc == 0
    conn = open_connection(str(db))
    cursor = conn.execute("SELECT COUNT(*) FROM chunks")
    chunk_count = cursor.fetchone()[0]
    docs = list_documents(conn)
    conn.close()
    assert len(docs) == 1
    assert docs[0].chunk_count == chunk_count


def test_rebuild_leaves_no_orphan_documents(tmp_path: Path) -> None:
    """Reindexing with --rebuild replaces the database cleanly."""
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "a.md").write_text("# A\n\nContent A.\n", encoding="utf-8")
    db = tmp_path / "docs.db"

    main([str(folder), "--db", str(db)])
    (folder / "b.md").write_text("# B\n\nContent B.\n", encoding="utf-8")

    rc = main([str(folder), "--db", str(db), "--rebuild"])

    assert rc == 0
    conn = open_connection(str(db))
    cursor = conn.execute("SELECT COUNT(*) FROM documents")
    count = cursor.fetchone()[0]
    conn.close()
    assert count == 2

# --- cross-layer: index for real, then read back ------------------------------

def test_indexed_document_reads_back_in_source_order(tmp_path: Path) -> None:
    """The seam test: CLI writes, store reads, order survives.

    Per-layer tests missed the lexicographic ordering defect because their
    fixtures never exceeded nine chunks. This one indexes a real file.
    """
    folder = tmp_path / "docs"
    folder.mkdir()
    body = "".join(
        f"## Section {i:02d}\n\n{'word ' * 40}marker{i:02d}\n\n" for i in range(15)
    )
    (folder / "long.md").write_text("# Title\n\n" + body, encoding="utf-8")
    db = tmp_path / "docs.db"

    assert main([str(folder), "--db", str(db)]) == 0

    conn = open_connection(str(db))
    try:
        text = "\n\n".join(get_chunks(conn, "long.md"))
    finally:
        conn.close()

    positions = [text.index(f"marker{i:02d}") for i in range(15)]
    assert positions == sorted(positions), "chunks came back out of order"


def test_chunk_index_is_contiguous_per_document(tmp_path: Path) -> None:
    """Skipped chunks must not leave gaps that break ordering assumptions."""
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "a.md").write_text(
        "# A\n\n" + "x" * 200 + "\n\n## B\n\n" + "y" * 200 + "\n",
        encoding="utf-8",
    )
    (folder / "b.md").write_text("# B\n\n" + "z" * 200 + "\n", encoding="utf-8")
    db = tmp_path / "docs.db"

    main([str(folder), "--db", str(db)])

    conn = open_connection(str(db))
    try:
        for doc in ("a.md", "b.md"):
            rows = conn.execute(
                "SELECT CAST(chunk_index AS INTEGER) FROM chunks "
                "WHERE document_path = ? ORDER BY 1",
                (doc,),
            ).fetchall()
            assert [r[0] for r in rows] == list(range(len(rows)))
    finally:
        conn.close()


# --- walking the folder -------------------------------------------------------

def test_nested_folders_are_indexed(tmp_path: Path) -> None:
    folder = tmp_path / "docs"
    (folder / "guides" / "deep").mkdir(parents=True)
    (folder / "top.md").write_text("# Top\n\n" + "a" * 200, encoding="utf-8")
    (folder / "guides" / "mid.md").write_text(
        "# Mid\n\n" + "b" * 200, encoding="utf-8"
    )
    (folder / "guides" / "deep" / "low.md").write_text(
        "# Low\n\n" + "c" * 200, encoding="utf-8"
    )
    db = tmp_path / "docs.db"

    assert main([str(folder), "--db", str(db)]) == 0

    conn = open_connection(str(db))
    try:
        paths = {d.path for d in list_documents(conn)}
    finally:
        conn.close()
    assert paths == {"top.md", "guides/mid.md", "guides/deep/low.md"}


def test_non_markdown_files_are_ignored(tmp_path: Path) -> None:
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "keep.md").write_text("# Keep\n\n" + "a" * 200, encoding="utf-8")
    (folder / "skip.txt").write_text("not markdown", encoding="utf-8")
    (folder / "skip.markdown").write_text("# No\n\nbody", encoding="utf-8")
    db = tmp_path / "docs.db"

    main([str(folder), "--db", str(db)])

    conn = open_connection(str(db))
    try:
        assert {d.path for d in list_documents(conn)} == {"keep.md"}
    finally:
        conn.close()


def test_nonexistent_folder_exits_1(tmp_path: Path) -> None:
    rc = main([str(tmp_path / "nope"), "--db", str(tmp_path / "d.db")])
    assert rc == 1
    assert not (tmp_path / "d.db").exists()


def test_file_instead_of_folder_exits_1(tmp_path: Path) -> None:
    target = tmp_path / "a.md"
    target.write_text("# A\n\nbody", encoding="utf-8")
    assert main([str(target), "--db", str(tmp_path / "d.db")]) == 1


def test_missing_db_argument_is_a_usage_error(tmp_path: Path) -> None:
    """--db is required; argparse must reject rather than default silently."""
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "a.md").write_text("# A\n\nbody", encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        main([str(folder)])
    assert exc.value.code == 2


# --- the CLI is allowed to use stdout; the server is not ----------------------

def test_cli_reports_progress_on_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "a.md").write_text("# A\n\n" + "a" * 200, encoding="utf-8")

    main([str(folder), "--db", str(tmp_path / "d.db")])

    out = capsys.readouterr().out
    assert "Indexed 1 files" in out


def test_existing_db_message_names_the_flag(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """SPEC: errors name the command to run, they do not just fail."""
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "a.md").write_text("# A\n\n" + "a" * 200, encoding="utf-8")
    db = tmp_path / "d.db"
    main([str(folder), "--db", str(db)])
    capsys.readouterr()

    rc = main([str(folder), "--db", str(db)])

    assert rc == 1
    assert "--rebuild" in capsys.readouterr().err


def test_rebuild_leaves_no_orphan_chunks(tmp_path: Path) -> None:
    """--rebuild drops removed files' chunks, not only their document rows."""
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "a.md").write_text("# A\n\n" + "a" * 200, encoding="utf-8")
    (folder / "gone.md").write_text("# Gone\n\n" + "g" * 200, encoding="utf-8")
    db = tmp_path / "docs.db"
    main([str(folder), "--db", str(db)])

    (folder / "gone.md").unlink()
    assert main([str(folder), "--db", str(db), "--rebuild"]) == 0

    conn = open_connection(str(db))
    try:
        remaining = conn.execute(
            "SELECT COUNT(*) FROM chunks WHERE document_path = 'gone.md'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert remaining == 0


# --- failure paths: previously uncovered, and previously masked ---------------

def test_programming_errors_are_not_reported_as_io_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bug in the chunker must surface, not be relabelled as an I/O error.

    The indexing loop used to catch bare `Exception`, so a TypeError from
    `chunk_markdown` reached the user as "I/O error" with exit code 2 —
    sending them to look at disk permissions instead of the parser.
    """
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "a.md").write_text("# A\n\n" + "a" * 200, encoding="utf-8")

    def exploding_chunker(source: str) -> object:
        raise TypeError("bad argument in _split_sections")

    monkeypatch.setattr(cli_module, "chunk_markdown", exploding_chunker)

    with pytest.raises(TypeError, match="_split_sections"):
        main([str(folder), "--db", str(tmp_path / "d.db")])


def test_database_creation_failure_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "a.md").write_text("# A\n\n" + "a" * 200, encoding="utf-8")

    def failing_create(db_path: str) -> object:
        raise StoreError("disk is full")

    monkeypatch.setattr(cli_module, "create_tables", failing_create)

    rc = main([str(folder), "--db", str(tmp_path / "d.db")])

    assert rc == 2
    assert "Could not create database" in capsys.readouterr().err


def test_store_failure_during_indexing_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "a.md").write_text("# A\n\n" + "a" * 200, encoding="utf-8")

    def failing_insert(conn: object, path: str, indexed_at: str) -> None:
        raise StoreError("database is locked")

    monkeypatch.setattr(cli_module, "insert_document", failing_insert)

    rc = main([str(folder), "--db", str(tmp_path / "d.db")])

    assert rc == 2
    err = capsys.readouterr().err
    assert "Indexing failed" in err
    assert "database is locked" in err


def test_undeletable_database_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--rebuild on a database the process cannot remove."""
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "a.md").write_text("# A\n\n" + "a" * 200, encoding="utf-8")
    db = tmp_path / "d.db"
    main([str(folder), "--db", str(db)])
    capsys.readouterr()

    def refuse_unlink(self: Path, missing_ok: bool = False) -> None:
        raise OSError("permission denied")

    monkeypatch.setattr(Path, "unlink", refuse_unlink)

    rc = main([str(folder), "--db", str(db), "--rebuild"])

    assert rc == 2
    assert "Could not remove" in capsys.readouterr().err


def test_oversized_chunk_is_skipped_with_a_warning(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A chunk over the store's limit warns and is skipped; the run continues."""
    folder = tmp_path / "docs"
    folder.mkdir()
    huge = "word " * 12000
    (folder / "big.md").write_text(f"# Big\n\n{huge}\n", encoding="utf-8")
    (folder / "ok.md").write_text("# Ok\n\n" + "a" * 200, encoding="utf-8")

    rc = main([str(folder), "--db", str(tmp_path / "d.db")])
    captured = capsys.readouterr()

    assert rc == 0
    assert "Warning: skipping chunk in big.md" in captured.err
    assert "Indexed 2 files" in captured.out
