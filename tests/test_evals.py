"""Tests for the retrieval evaluation harness.

The harness is what the README's headline numbers come from, so it needs to
fail loudly rather than silently drift.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import pytest

from mcp_docs_search.cli import main as index_folder
from mcp_docs_search.store import list_documents, open_connection, search

EVALS_DIR = Path(__file__).resolve().parent.parent / "evals"
FIXTURES_DIR = EVALS_DIR / "fixtures"
QUESTIONS_FILE = EVALS_DIR / "questions.toml"


def _questions() -> list[dict[str, Any]]:
    with open(QUESTIONS_FILE, "rb") as handle:
        data: dict[str, Any] = tomllib.load(handle)
    questions: list[dict[str, Any]] = data["question"]
    return questions


def test_questions_file_parses() -> None:
    assert len(_questions()) >= 15, "SPEC section 7 asks for 15-20 questions"


def test_every_question_has_both_fields() -> None:
    for question in _questions():
        assert question.get("query", "").strip()
        assert question.get("expected_source", "").strip()


def test_every_expected_source_exists_in_fixtures() -> None:
    """A typo in expected_source silently caps recall at less than 1.0."""
    available = {p.name for p in FIXTURES_DIR.glob("*.md")}
    referenced = {q["expected_source"] for q in _questions()}
    assert referenced <= available, f"missing fixtures: {referenced - available}"


def test_no_duplicate_queries() -> None:
    queries = [q["query"] for q in _questions()]
    assert len(queries) == len(set(queries))


def test_fixtures_are_not_empty() -> None:
    fixtures = list(FIXTURES_DIR.glob("*.md"))
    assert fixtures
    for fixture in fixtures:
        assert fixture.read_text(encoding="utf-8").strip()


@pytest.fixture
def eval_db(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Path:
    db = tmp_path / "evals.db"
    assert index_folder([str(FIXTURES_DIR), "--db", str(db), "--rebuild"]) == 0
    capsys.readouterr()
    return db


def test_every_fixture_is_indexed(eval_db: Path) -> None:
    conn = open_connection(str(eval_db))
    try:
        indexed = {d.path for d in list_documents(conn)}
    finally:
        conn.close()
    assert indexed == {p.name for p in FIXTURES_DIR.glob("*.md")}


def test_every_question_returns_at_least_one_result(eval_db: Path) -> None:
    """A question that matches nothing is a broken question, not a low score."""
    conn = open_connection(str(eval_db))
    try:
        empty = [
            q["query"] for q in _questions() if not search(conn, q["query"], 3)
        ]
    finally:
        conn.close()
    assert empty == [], f"queries with no results at all: {empty}"


def test_recall_is_reported_and_within_range(
    eval_db: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Guards the harness itself: it must run and print parseable metrics."""
    from evals.run_evals import run_questions

    run_questions(eval_db, _questions())
    out = capsys.readouterr().out

    assert "recall@1:" in out and "recall@3:" in out
    scores = [
        float(part.split(":")[1].strip())
        for part in out.split("   ")
        if part.strip().startswith(("recall@1", "recall@3"))
    ]
    assert len(scores) == 2
    assert all(0.0 <= score <= 1.0 for score in scores)
    assert scores[0] <= scores[1], "recall@1 cannot exceed recall@3"


def test_harness_reports_the_documents_it_failed_on(
    eval_db: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """SPEC section 7: failing queries must be listed so they can be reasoned about."""
    from evals.run_evals import run_questions

    run_questions(eval_db, [{"query": "zzz nonexistent term", "expected_source": "logging.md"}])
    out = capsys.readouterr().out

    assert "Failures:" in out
    assert "logging.md" in out
