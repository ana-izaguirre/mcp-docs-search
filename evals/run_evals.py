"""Retrieval evaluation harness for mcp-docs-search.

Builds an index from evals/fixtures/ by calling the indexing CLI (cli.main)
with crafted argv, so the walk logic lives in one place, then runs every
question through the same query path the MCP server uses.

Beyond the absolute recall figures, the harness compares against a saved
baseline and reports how many questions a change fixed and how many it broke.
That comparison is what the shipping rule in the README rests on: two recall
percentages can move without the difference meaning anything, and the number
of discordant questions is what decides whether it does.

    python evals/run_evals.py                  # measure, and compare if a baseline exists
    python evals/run_evals.py --save-baseline  # record the current run as the baseline
"""

import argparse
import contextlib
import io
import json
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import NamedTuple

from mcp_docs_search.cli import main as index_folder
from mcp_docs_search.store import (
    list_documents,
    open_connection,
    search,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
QUESTIONS_FILE = Path(__file__).parent / "questions.toml"
BASELINE_FILE = Path(__file__).parent / "baseline.json"

TOP_K = 3
# Below this many discordant questions, an exact one-sided binomial test cannot
# reach p < 0.05, so the change is indistinguishable from luck no matter how
# good the recall percentages look.
MIN_DISCORDANT_FOR_SIGNIFICANCE = 5


class Outcome(NamedTuple):
    """What happened to one question."""

    query: str
    expected: str
    rank: int | None  # 1-based rank of the expected document, None if absent
    retrieved: list[str]


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


def evaluate(db_path: Path, questions: list[dict[str, str]]) -> list[Outcome]:
    """Run every question and record where the expected document ranked."""
    conn = open_connection(str(db_path))
    try:
        outcomes = []
        for question in questions:
            expected = question["expected_source"]
            documents = [r[1] for r in search(conn, question["query"], TOP_K)]
            rank = documents.index(expected) + 1 if expected in documents else None
            outcomes.append(
                Outcome(question["query"], expected, rank, documents)
            )
    finally:
        conn.close()
    return outcomes


def _exact_binomial_p(fixed: int, broken: int) -> float:
    """One-sided exact binomial p-value over the discordant questions.

    McNemar's test: only questions whose outcome changed carry information.
    Under the null hypothesis a change is as likely to break a question as to
    fix one, so this is the chance of seeing at least `fixed` improvements out
    of `fixed + broken` coin flips.
    """
    n = fixed + broken
    if n == 0:
        return 1.0

    def choose(total: int, k: int) -> int:
        result = 1
        for i in range(k):
            result = result * (total - i) // (i + 1)
        return result

    tail = sum(choose(n, k) for k in range(fixed, n + 1))
    return tail / (1 << n)  # 2**n, but typed as int rather than Any


def _metrics(outcomes: list[Outcome]) -> tuple[float, float, float]:
    """Return recall@1, recall@3 and mean reciprocal rank."""
    n = len(outcomes)
    if not n:
        return 0.0, 0.0, 0.0
    recall1 = sum(1 for o in outcomes if o.rank == 1) / n
    recall3 = sum(1 for o in outcomes if o.rank is not None) / n
    mrr = sum(1.0 / o.rank for o in outcomes if o.rank is not None) / n
    return recall1, recall3, mrr


def _report_comparison(outcomes: list[Outcome], baseline: dict[str, int]) -> None:
    """Print what changed against the baseline, and whether it is defensible."""
    fixed = []
    broken = []
    for outcome in outcomes:
        was = baseline.get(outcome.query)
        if was is None:
            continue  # question did not exist in the baseline
        now_hit = outcome.rank == 1
        was_hit = was == 1
        if now_hit and not was_hit:
            fixed.append(outcome.query)
        elif was_hit and not now_hit:
            broken.append(outcome.query)

    print()
    print(f"Against baseline: fixed {len(fixed)}, broke {len(broken)}")

    for query in fixed:
        print(f"  + {query}")
    for query in broken:
        print(f"  - {query}")

    discordant = len(fixed) + len(broken)
    if discordant == 0:
        print("  no question changed outcome at rank 1")
        return

    p = _exact_binomial_p(len(fixed), len(broken))
    verdict = "significant" if p < 0.05 else "indistinguishable from noise"
    print(f"  exact binomial p = {p:.3f} over {discordant} discordant -> {verdict}")
    if p >= 0.05:
        print(
            f"  (at least {MIN_DISCORDANT_FOR_SIGNIFICANCE} net fixes are needed "
            f"before a change can be defended)"
        )


def report(
    outcomes: list[Outcome], documents: int, chunks: int, baseline: dict[str, int] | None
) -> None:
    """Print metrics, failures, and the comparison against any baseline."""
    recall1, recall3, mrr = _metrics(outcomes)
    print(
        f"recall@1: {recall1:.2f}   recall@3: {recall3:.2f}   MRR: {mrr:.2f}   "
        f"({len(outcomes)} queries, {documents} documents, {chunks} chunks)"
    )

    failures = [o for o in outcomes if o.rank is None]
    if failures:
        print()
        print("Failures:")
        for outcome in failures:
            got = ", ".join(outcome.retrieved) if outcome.retrieved else "(no results)"
            print(f'  "{outcome.query}"')
            print(f"    expected {outcome.expected}, got {got}")

    if baseline is not None:
        _report_comparison(outcomes, baseline)


def load_questions() -> list[dict[str, str]]:
    with open(QUESTIONS_FILE, "rb") as handle:
        data: dict[str, list[dict[str, str]]] = tomllib.load(handle)
    return data["question"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run_evals")
    parser.add_argument(
        "--save-baseline",
        action="store_true",
        help="record this run as the baseline future runs compare against",
    )
    args = parser.parse_args(argv)

    questions = load_questions()

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "evals.db"
        build_index(db_path, FIXTURES_DIR)

        outcomes = evaluate(db_path, questions)

        conn = open_connection(str(db_path))
        docs = list_documents(conn)
        conn.close()

    baseline: dict[str, int] | None = None
    if BASELINE_FILE.exists() and not args.save_baseline:
        with open(BASELINE_FILE, encoding="utf-8") as handle:
            stored: dict[str, int] = json.load(handle)
        baseline = stored

    report(outcomes, len(docs), sum(d.chunk_count for d in docs), baseline)

    if args.save_baseline:
        ranks = {o.query: (o.rank if o.rank is not None else 0) for o in outcomes}
        with open(BASELINE_FILE, "w", encoding="utf-8") as handle:
            json.dump(ranks, handle, indent=2, sort_keys=True)
            handle.write("\n")
        print()
        print(f"Baseline written to {BASELINE_FILE.name} ({len(ranks)} questions)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
