# mcp-docs-search Tasks

Derived from [`SPEC.md`](../SPEC.md) and [`AGENTS.md`](../AGENTS.md). Each task
is self-contained, with acceptance criteria and dependency ordering.

Status legend: `[x]` done · `[~]` partially done · `[ ]` not started.

## Tasks

### Task 1 — SQLite FTS5 store (`store.py`) — `[x]`
**Depends on:** nothing

- [x] `create_tables(db_path)` creates `documents` and `chunks`; refuses an
      existing file with an actionable `StoreError`
- [x] `insert_document(conn, path, indexed_at)`
- [x] `insert_chunk(conn, chunk_id, document_path, heading_path, content,
      chunk_index)` — rejects empty content, content over 50 000 characters,
      and a negative `chunk_index`
- [x] `search(conn, query, limit)` and `search_with_score(...)` — validate the
      query, clamp `limit` to 1–20, `ORDER BY rank` ascending
- [x] `sanitise_query(query)` turns free text into literal FTS5 terms
- [x] `get_chunks(conn, path)` returns a document in order (`ORDER BY CAST(
      chunk_index AS INTEGER)`)
- [x] `list_documents(conn)` returns path, indexed_at and chunk count
- [x] Only `store.py` imports `sqlite3`; failures surface as `StoreError`
- [x] Tests in `tests/test_store.py`, including boundaries and failure paths

### Task 2 — Heading-based chunking (`ingest.py`) — `[x]`
**Depends on:** nothing (pure module, no storage)

- [x] `chunk_markdown(source)` — text in, `Chunk` objects out; no filesystem
- [x] `format_heading_path(rel_path, heading_path)`
- [x] Each `#`/`##`/`###` section is one chunk carrying its full heading path
- [x] Sections over 1500 characters split at paragraph boundaries
- [x] Sections under 100 characters merge into the next one; merge runs before
      split, and split chunks are never re-merged
- [x] Headings inside fenced code blocks are not headings
- [x] Trailing MkDocs `attr_list` anchors are stripped from heading text
- [x] Tests in `tests/test_ingest.py`

### Task 3 — Indexing CLI (`cli.py`) — `[x]`
**Depends on:** tasks 1, 2

- [x] `mcp-docs-search <folder> --db <path> [--rebuild]`, no subcommand
- [x] Walks `.md` files recursively; stored paths are relative and use forward
      slashes on every platform
- [x] Refuses an existing database unless `--rebuild`, naming the flag
- [x] Records one `documents` row per indexed file
- [x] Skips unreadable files without aborting the run
- [x] Writes progress to stdout and problems to stderr
- [x] Tests in `tests/test_cli.py`

### Task 4 — MCP server (`server.py`) — `[x]`
**Depends on:** tasks 1, 3

- [x] `search_docs(query, limit=5)`, `list_sources()`, `get_document(path)`
- [x] `limit` clamped to 1–20; empty query returns `[]`, not an error
- [x] Serves only paths present in the index — no filesystem access at runtime
- [x] Nothing writes to stdout, on success or failure paths
- [x] Actionable message when the database is missing, then exit 1
- [x] Tests in `tests/test_server.py`, including tool registration

### Task 5 — README — `[x]`
**Depends on:** task 4

- [x] Problem, quick start, tool table, how it works, scope, how it was built
- [x] Retrieval quality section filled with measured numbers
- [x] How to verify the server locally
- [x] Demo GIF of a real client session (see task 9)

### Task 6 — Evals and fixtures — `[x]`
**Depends on:** tasks 2, 4

- [x] `evals/run_evals.py` builds an index from the fixtures and reports
      recall@1, recall@3 and the failing queries
- [x] `evals/questions.toml` — 15 entries of `query` + `expected_source`
- [x] Tests in `tests/test_evals.py` guard the harness and the question set
- [x] Questions rewritten blind — phrased from a user's point of view, never
      copying the vocabulary of the file they should find
- [x] `evals/fixtures/` grown to 21 files

### Task 7 — CI — `[x]`
**Depends on:** tasks 1, 4

- [x] `uv run pytest` and `mypy --strict` on push and pull request
- [x] Ubuntu and Windows matrix
- [x] Smoke test of the published console scripts
- [x] Eval harness runs in CI so the README numbers cannot silently drift

### Task 8 — `docs/decisions.md` — `[x]`
**Depends on:** tasks 1, 2, 4

- [x] The four foundational entries: FTS5 over a vector store, heading-based
      chunking over fixed windows, retrieval without generation, and
      `get_document` alongside `search_docs`
- [x] Implementation decisions worth questioning later
- [x] Format: **Context → Proposed → Decided → Why**

### Task 9 — Demo — `[x]`
**Depends on:** tasks 4, 6

- [x] `scripts/mcp_smoke.py` drives the live server over stdio
- [x] `scripts/demo-checklist.md` with the recording steps
- [x] `scripts/demo.tape` so the GIF renders from one command
- [x] `docs/demo-transcript.md` captured from a real run
- [x] Record the GIF and link it from the README — `scripts/demo.tape`
      rendered to `docs/demo.gif`, covering indexing and the live stdio
      session. The agent half stays unscripted; the checklist keeps the
      steps for recording it live.

### Task 10 — Integration coverage — `[x]`
**Depends on:** tasks 3, 4

- [x] `tests/test_integration.py` runs the published console scripts as
      subprocesses and drives the server over a real stdio MCP session
- [x] Covers the wiring SPEC section 8 lists as a known gap: `project.scripts`,
      argument parsing and default paths

## How to verify a task

```bash
uv run pytest
uv run mypy --strict src/ tests/ evals/ scripts/
uv run python evals/run_evals.py
```

Do not mark a task done without the actual output.
