"""Retrieval evaluation harness for mcp-docs-search.

Builds an index from evals/fixtures/ by calling the indexing CLI (cli.main)
with crafted argv, so the walk logic lives in one place. Runs each question
through store.search and reports recall@1 and recall@3.
"""

import contextlib
import io
import sys
import tempfile
import tomllib
from pathlib import Path

from mcp_docs_search.cli import main as index_folder
from mcp_docs_search.store import (
    list_documents,
    open_connection,
    search,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
QUESTIONS_FILE = Path(__file__).parent / "questions.toml"


def build_index(db_path: Path, fixtures_dir: Path) -> None:
    """Index fixtures_dir into db_path using the CLI's indexing path.

    cli.main prints progress to stdout; suppress it so it doesn't pollute
    the eval output.
    """
    argv = [str(fixtures_dir), "--db", str(db_path), "--rebuild"]
    with contextlib.redirect_stdout(io.StringIO()):
        exit_code = index_folder(argv)
    if exit_code != 0:
        raise RuntimeError(f"Indexing failed with exit code {exit_code}")


def run_questions(db_path: Path, questions: list[dict]) -> None:
    """Run all questions and report recall metrics."""
    conn = open_connection(str(db_path))
    try:
        recall1_hits = 0
        recall3_hits = 0
        failures: list[tuple[str, str, list[str]]] = []

        for q in questions:
            query = q["query"]
            expected = q["expected_source"]

            results = search(conn, query, limit=3)
            documents = [r[1] for r in results]

            top1 = documents[0] if documents else ""
            top3 = documents[:3]

            if top1 == expected:
                recall1_hits += 1
            if expected in top3:
                recall3_hits += 1
            else:
                failures.append((query, expected, top3))
    finally:
        conn.close()

    n = len(questions)
    recall1 = recall1_hits / n if n else 0.0
    recall3 = recall3_hits / n if n else 0.0

    conn = open_connection(str(db_path))
    try:
        docs = list_documents(conn)
    finally:
        conn.close()
    total_chunks = sum(d.chunk_count for d in docs)

    print(
        f"recall@1: {recall1:.2f}   recall@3: {recall3:.2f}   "
        f"({n} queries, {len(docs)} documents, {total_chunks} chunks)"
    )

    if failures:
        print()
        print("Failures:")
        for query, expected, got in failures:
            got_str = ", ".join(got) if got else "(no results)"
            print(f'  "{query}"')
            print(f"    expected {expected}, got {got_str}")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "evals.db"

        build_index(db_path, FIXTURES_DIR)

        with open(QUESTIONS_FILE, "rb") as f:
            data = tomllib.load(f)

        questions = data["question"]
        run_questions(db_path, questions)

    return 0


if __name__ == "__main__":
    sys.exit(main())
