"""Tests for the indexing CLI."""

from pathlib import Path

from mcp_docs_search.cli import main
from mcp_docs_search.store import open_connection


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