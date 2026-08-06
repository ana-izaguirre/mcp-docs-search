# docs-mcp Tasks — Phase 1

## Introduction

Based on SPEC.md and AGENTS.md, this list breaks Phase 1 into small, verifiable tasks with clear acceptance criteria and dependency ordering. Tasks are self-contained — only tasks dependent on the database or chunking implemented in this phase.

## Tasks

### Task 1: Implement SQLite FTS5 (store.py)
**Depends on:** None (starting point)

- [ ] Implement `src/docs_mcp/store.py` with:
  - `create_tables()` — creates `documents` and `chunks` tables (no `headings` table)
  - `insert_chunk(chunk_id, document_path, heading_path, content)` (no `score`)
  - `search(query, limit)` — returns `(chunk_id, document_path, heading_path, content, score)`
- [ ] `create_tables()` fails gracefully if the .db file already exists (no --rebuild logic here)
- [ ] `search()` validates `limit` (1-20), rejects empty query
- [ ] `insert_chunk()` rejects empty `content`, length > 50000
- [ ] Public members with type hints; `mypy --strict` passes
- [ ] Tests in `tests/test_store.py`:
  - table creation test
  - insert test
  - search test with relevant paragraph

**Abbreviation:** "Store works and validates"

### Task 2: Heading-based chunking (ingest.py)
**Depends on:** Task 1

- [ ] Implement `src/docs_mcp/ingest.py` with:
  - `scan_directory(root)` — returns list of .md/.mdx paths
  - `parse_file(path)` — returns `(document_path, chunks)` where each chunk is `(heading_path, content)`
- [ ] Heading-based chunking:
  - Each section (#, ##, ###) is a chunk
  - Length >1500 → split by paragraph maintaining heading
  - Length <100 → merge with next
  - Heading path preserved: `"guia.md > Instalación > Configuración"`
- [ ] `parse_file()` normalizes line separators, removes empty lines at start/end
- [ ] Public members with type hints; `mypy --strict` passes
- [ ] Tests in `tests/test_chunking.py`:
  - heading-based chunking test
  - long section split test
  - short section merge test

**Abbreviation:** "Heading-based chunking works"

### Task 3: Index CLI (cli.py)
**Depends on:** Task 1, Task 2

- [ ] Implement `src/docs_mcp/cli.py` with:
  - `index_command(root, db_path)`
- [ ] `index_command()`:
  - Rejects path outside `root` (path traversal)
  - Rejects if db exists without --rebuild (message actionable)
  - Scans, parses, inserts chunks using store
  - Logs to stderr only
- [ ] Public members with type hints; `mypy --strict` passes
- [ ] Tests in `tests/test_cli.py`:
  - index command test with --rebuild
  - edge cases

**Abbreviation:** "Index CLI works"

### Task 4: MCP server (server.py)
**Depends on:** Task 1, Task 3

- [ ] Implement `src/docs_mcp/server.py` with FastMCP:
  - `search_docs(query, limit=5)`
  - `list_sources()`
  - `get_document(path)`
- [ ] `search_docs()` validates query (not empty), clamps limit (1-20)
- [ ] Rejects file access outside indexed directory (path traversal)
- [ ] No output to stdout (logging to stderr only)
- [ ] Tool routes registered with FastMCP
- [ ] Public members with type hints; `mypy --strict` passes
- [ ] Tests in `tests/test_tools.py`:
  - search_docs test
  - list_sources test
  - get_document test with path traversal rejection

**Abbreviation:** "MCP server works"

### Task 5: README with required sections
**Depends on:** Task 4

- [ ] Write `README.md` with required sections from SPEC section 9:
  1. **The problem** — the agent doesn't know your internal documentation. Three lines.
  2. **Quick start** — index and connect, with copyable MCP client config block.
  3. **Tools** — table from SPEC section 3.
  4. **How it works** — heading-based chunking and FTS5, with decision rationale.
  5. **Retrieval quality** — eval numbers (placeholder for now).
  6. **Roadmap** — "Phase 2: embeddings on same SQLite, measured against this baseline."
  7. **How this was built** — agent workflow. Links to `AGENTS.md` and `docs/decisions.md`.
  8. **Demo** — GIF of a real session.
- [ ] Placeholder for Retrieval quality (actual numbers from Task 6)

**Abbreviation:** "README complete"

### Task 6: Evals and fixtures (run_evals.py, questions.yaml)
**Depends on:** Task 2, Task 4

- [ ] Implement `evals/run_evals.py`:
  - Loads `evals/questions.yaml`
  - For each query runs `search_docs`
  - Calculates recall@1 and recall@3
  - Prints JSON response for README
- [ ] Implement `evals/fixtures/` with ~20 representative .md files
- [ ] `questions.yaml` structure: `query` + `expected_source`
- [ ] `run_evals.py` rejects if db doesn't exist (actionable message)
- [ ] Public members with type hints; `mypy --strict` passes
- [ ] Tests in `tests/test_evals.py`:
  - evals basic test
  - fixture files test

**Abbreviation:** "Evals work"

### Task 7: GitHub Actions (ci.yml)
**Depends on:** Task 1, Task 4

- [ ] Implement `.github/workflows/ci.yml`:
  - Runs `uv run pytest` on push/pr
  - Runs `uv run mypy --strict src/` on push/pr
- [ ] CI fails if tests or mypy fail

**Abbreviation:** "CI set up"

### Task 8: docs/decisions.md with key decisions
**Depends on:** Task 1, Task 2, Task 4

- [ ] Write entries for natural decisions:
  - Why FTS5 and not vector store from the start
  - Why heading-based chunking and not fixed-size windows
  - Why server doesn't generate answers
  - Why `get_document` exists alongside `search_docs`
- [ ] Format: **Context → What was proposed → What was decided → Why**

**Abbreviation:** "Decisions documented"

### Task 9: Demo GIF recording checklist
**Depends on:** Task 4, Task 6

- [ ] Create `scripts/demo-checklist.md` with manual steps:
  - Run `docs-mcp index ./evals/fixtures/demo.db --rebuild`
  - Open OpenCode, connect to running MCP server
  - Ask 2-3 questions from evals/questions.yaml
  - Capture agent's answers with source citations
  - Record screen with these steps
  - Save transcript to `docs/demo-transcript.md`
  - Generate GIF, upload to repo

**Abbreviation:** "Demo checklist ready"

## Summary

- **9 total tasks** (under the limit)
- **All self-contained** with clear acceptance criteria
- **Dependency ordering** respects logical flow
- **Each requires tests first** before implementation
- **List ready to start**

## How to verify each task

1. Run `uv run pytest` → show test output
2. Run `uv run mypy --strict src/` → must pass
3. Show error if any stage fails before the next
4. Don't mark any as complete without actual evidence

When a task is ready (tests pass, mypy passes, commits made), mark it and move to the next.
