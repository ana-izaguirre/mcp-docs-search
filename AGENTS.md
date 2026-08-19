# AGENTS.md

## Project

`mcp-docs-search` — an MCP server that indexes a folder of markdown
documentation and exposes keyword search to an AI agent. Written in Python,
backed by SQLite FTS5.

The full specification lives in [`SPEC.md`](./SPEC.md). Read it before starting
any task. The task breakdown is in [`docs/tasks.md`](./docs/tasks.md).

## Scope boundaries — do not cross these

This is Phase 1. The following are explicitly **out of scope** and must not be
implemented, suggested, or scaffolded for:

- Embeddings, vector search, or any RAG technique (that is Phase 2)
- Any call to an LLM or external API
- Answer generation — this server retrieves, the agent generates
- Web UI, PDF ingestion, incremental reindexing, reranking

If a task seems to require any of these, stop and ask instead of implementing.

## Technical constraints

- **Python 3.12.** Type hints on every public function. `mypy --strict` must
  pass over `src/`, `tests/`, `evals/` and `scripts/`. No `Any`, no
  `type: ignore`.
- **One runtime dependency:** the `mcp` package. Everything else comes from the
  standard library. Adding a dependency requires explicit justification and
  approval — never add one unilaterally. This is why the eval question set is
  TOML (stdlib `tomllib`) rather than YAML.
- Storage is SQLite with FTS5, from the stdlib `sqlite3` module. No ORM, no
  migration tool, no external database.
- **Never write to stdout in the server.** stdout is the MCP protocol channel.
  All server logging goes to stderr via the `logging` module. A `print()`
  anywhere in `src/mcp_docs_search/server.py`, or in anything it imports, is a
  bug. The CLI is a separate entry point and *does* write progress to stdout.
- **Storage isolation.** Only `store.py` imports `sqlite3`. It raises
  `StoreError`; nothing above it knows the storage engine. This is what lets
  Phase 2 add embeddings without touching the server.
- **Parsing is pure.** `ingest.py` does not touch the filesystem and does not
  import `store.py`. Text in, chunks out. Reading files and walking directories
  belong to the CLI layer.
- Validate tool inputs at the boundary. `limit` is clamped to 1–20, never
  rejected. An empty or whitespace-only query returns an empty list, not an
  error.
- **No filesystem access at runtime.** `get_document` serves only paths already
  in the index, so path traversal is structurally impossible rather than
  filtered.
- **Free-text queries are sanitised** into literal FTS5 terms before matching,
  so operator characters (`*`, `"`, `NEAR(`, `OR`) cannot raise or trigger a
  full index scan.
- Errors returned to the agent must be actionable **by the agent** — it cannot
  read server logs. "Database not found — run `mcp-docs-search ./docs --db
  ./docs.db`" is correct. A raw `sqlite3.OperationalError` is not.
- The `chunks` table is FTS5: no column types, no constraints, no external
  indexes. Ordering metadata (`chunk_index`) is an `UNINDEXED` column, and
  `get_chunks` casts it to INTEGER — FTS5 stores columns as text, so a plain
  `ORDER BY` sorts lexicographically.
- FTS5 ranking uses `ORDER BY rank` ascending — `bm25()` returns negative
  values where more negative means more relevant. Never `DESC`.

## Workflow

- Work in thin vertical slices. One tool or one module per task, not three at
  once.
- Tests before implementation. A task is not started until its test exists and
  fails.
- **At least one test per feature must cross the whole system.** Per-layer
  tests pass while the seams between them are broken — that is how the empty
  `documents` table and the scrambled `get_document` output both shipped. See
  `tests/test_integration.py`.
- Commit after each task passes. Small commits, present-tense messages.
- Commit messages follow Conventional Commits: `<type>: <imperative
  description>`. Types: feat, fix, docs, test, refactor, chore, ci, perf.
  Lowercase after the colon, no trailing period, under 72 characters.
- Never mark a task done without showing the actual test output.
- Tests import from the installed package path (`mcp_docs_search.x`), never a
  bare module name.
- Tests use pytest's `tmp_path` fixture, never `tempfile` with manual cleanup.
- Do not implement functions belonging to other tasks in `docs/tasks.md`, even
  if they seem necessary. Each task has a closed scope — but say so when a task
  leaves a seam uncovered.

## Definition of done, per task

- [ ] Test written first, in the same response as the implementation
- [ ] Failure paths and boundaries tested, not only the happy path
- [ ] Type hints on every public function; no `Any`, no `type: ignore`
- [ ] No `print()` in the server or anything it imports
- [ ] Only stdlib plus `mcp`
- [ ] `uv run pytest` and `uv run mypy --strict src/ tests/ evals/ scripts/` pass
- [ ] README and `docs/tasks.md` updated if the change is user-visible

## Commands

```bash
uv sync                                             # install
uv run pytest                                       # tests
uv run mypy --strict src/ tests/ evals/ scripts/    # types
uv run mcp-docs-search ./docs --db ./docs.db --rebuild   # build an index
uv run python scripts/mcp_smoke.py --db ./docs.db   # exercise the live server
uv run python evals/run_evals.py                    # retrieval metrics
```

## Decision log

When you propose an approach and it is overridden, append the exchange to
[`docs/decisions.md`](./docs/decisions.md) in this format:

**Context → What was proposed → What was decided → Why**

Do not write entries for trivial choices. Only decisions a future reader would
otherwise question.
