"""Indexing CLI: wires ingest to store."""

import argparse
import sys
from pathlib import Path

from mcp_docs_search.ingest import chunk_markdown, format_heading_path
from mcp_docs_search.store import create_tables, insert_chunk


def main(argv: list[str] | None = None) -> int:
    """Index a folder of markdown files into a SQLite FTS5 database.

    Args:
        argv: Command-line arguments (defaults to ``sys.argv[1:]`` if
            ``None``).

    Returns:
        Exit code: 0 for success, 1 for usage or precondition error, 2
        for I/O error.
    """
    parser = argparse.ArgumentParser(
        prog="mcp-docs-search",
        description="Index a folder of markdown documentation for search.",
    )
    parser.add_argument("folder", help="Folder to index")
    parser.add_argument(
        "--db", required=True, help="Path to the SQLite database file",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Delete and recreate the database if it already exists",
    )

    args = parser.parse_args(argv)
    folder = Path(args.folder)
    db_path = Path(args.db)

    if not folder.is_dir():
        print(f"Not a directory: {folder}", file=sys.stderr)
        return 1

    md_files = sorted(f for f in folder.rglob("*.md") if f.is_file())

    if not md_files:
        print(f"No .md files found in {folder}", file=sys.stderr)
        return 1

    if db_path.exists():
        if args.rebuild:
            try:
                db_path.unlink()
            except OSError as e:
                print(f"Could not remove {db_path}: {e}", file=sys.stderr)
                return 2
        else:
            print(
                f"Database already exists: {db_path}. "
                f"Use --rebuild to recreate it.",
                file=sys.stderr,
            )
            return 1

    try:
        conn = create_tables(str(db_path))
    except Exception as e:
        print(f"Could not create database: {e}", file=sys.stderr)
        return 2

    files_indexed = 0
    chunks_written = 0
    files_skipped = 0

    try:
        for file_idx, file_path in enumerate(md_files):
            rel_path = file_path.relative_to(folder).as_posix()

            try:
                source = file_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as e:
                print(f"Skipping {rel_path}: {e}", file=sys.stderr)
                files_skipped += 1
                continue

            chunks = chunk_markdown(source)

            for chunk_idx, chunk in enumerate(chunks):
                if not chunk.text.strip():
                    continue
                chunk_id = f"{file_idx}_{chunk_idx}"
                heading_path_str = format_heading_path(
                    rel_path, chunk.heading_path,
                )
                try:
                    insert_chunk(
                        conn, chunk_id, rel_path, heading_path_str, chunk.text,
                    )
                    chunks_written += 1
                except ValueError as e:
                    print(
                        f"Warning: skipping chunk in {rel_path}: {e}",
                        file=sys.stderr,
                    )

            files_indexed += 1

        conn.commit()
    except Exception as e:
        print(f"I/O error: {e}", file=sys.stderr)
        return 2
    finally:
        conn.close()

    print(
        f"Indexed {files_indexed} files, "
        f"{chunks_written} chunks, "
        f"{files_skipped} skipped",
    )
    return 0