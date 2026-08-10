# docs-mcp — Setup de OpenCode
---

## Paso 0 — Preparar el repo (15 min, una sola vez)

```bash
mkdir docs-mcp && cd docs-mcp
git init
uv init --package docs-mcp
```

Instalar las skills. **Solo estas cuatro** — no las 24, que llenan el contexto con cosas de frontend que aquí no aplican:

```bash
npx skills add addyosmani/agent-skills --skill test-driven-development
npx skills add addyosmani/agent-skills --skill incremental-implementation
npx skills add addyosmani/agent-skills --skill planning-and-task-breakdown
npx skills add addyosmani/agent-skills --skill documentation-and-adrs
```

Guardar `spec-docs-mcp-fase1.md` en la raíz como `SPEC.md`, y crear el `AGENTS.md` de la sección siguiente.

---

## AGENTS.md — pegar tal cual en la raíz del repo

```markdown
# AGENTS.md

## Project

`docs-mcp` — an MCP server that indexes a folder of markdown documentation and
exposes keyword search to an AI agent. Written in Python.

The full specification lives in `SPEC.md`. Read it before starting any task.

## Scope boundaries — do not cross these

This is Phase 1. The following are explicitly **out of scope** and must not be
implemented, suggested, or scaffolded for:

- Embeddings, vector search, or any RAG technique (that is Phase 2)
- Any call to an LLM or external API
- Answer generation — this server retrieves, the agent generates
- Web UI, PDF ingestion, incremental reindexing, reranking

If a task seems to require any of these, stop and ask instead of implementing.

## Technical constraints

- Python 3.11+. Type hints on every public function. `mypy --strict` must pass.
- Only one runtime dependency: the `mcp` package. Everything else comes from the
  standard library. Adding a dependency requires explicit justification and my
  approval — do not add one unilaterally.
- Storage is SQLite with FTS5, from the stdlib `sqlite3` module. Do not introduce
  an ORM, a migration tool, or an external database.
- **Never write to stdout.** stdout is the MCP protocol channel. All logging goes
  to stderr via the `logging` module. A `print()` anywhere in `src/` is a bug.
- Validate tool inputs at the boundary. `limit` is clamped to 1-20. A `path`
  outside the indexed folder is rejected — no path traversal.
- Errors returned to the agent must be actionable. "Database not found — run
  `docs-mcp index ./docs`" is correct. A raw `sqlite3.OperationalError` is not.
- The `chunks` table is FTS5: no column types, no constraints, no external
  indexes. FTS5 maintains its own inverted index.
- FTS5 ranking uses `ORDER BY rank` ascending — bm25() returns negative
  values where more negative means more relevant. Never `DESC`.

## Workflow

- Work in thin vertical slices. One tool or one module per task, not three at once.
- Tests before implementation. A task is not started until its test exists and fails.
- Commit after each task passes. Small commits, present-tense messages.
- Commit messages follow Conventional Commits: `<type>: <imperative description>`.
  Types: feat, fix, docs, test, refactor, chore, ci, perf.
  Lowercase after the colon, no trailing period, under 72 characters.
- Never mark a task done without showing the actual test output.
- Tests import from the installed package path (`mcp_docs_search.x`), never a
  bare module name.
- Tests use pytest's `tmp_path` fixture, never tempfile with manual cleanup.
- Do not execute commands. Not git, not uv, not pytest, not shell of any kind.
  Assume the repository and environment are in the state described in the prompt.
- Do not read files from the repository. All necessary context is in the prompt.
  If something is missing, say so and stop.
- If you believe a command must be run, state which one and why, then stop.
- Do not implement functions belonging to other tasks in docs/tasks.md, even if
  they seem necessary. Each task has a closed scope.
- Parsing modules do not import sqlite3 or store.py. Persistence is wired in
  the CLI layer.

## Definition of done, per task

Yours (the agent):
- [ ] Test written first, in the same response as the implementation
- [ ] Type hints on every public function; no `Any`, no `type: ignore`
- [ ] No `print()` anywhere in `src/`
- [ ] Only stdlib plus `mcp`

Mine (the human) — do not attempt these:
- [ ] Running pytest and mypy
- [ ] Verifying output
- [ ] Committing

## Commands

```bash
uv run pytest              # tests
uv run mypy --strict src/  # types
uv run docs-mcp index ./docs --db ./docs.db
uv run python evals/run_evals.py
```

## Decision log

When you propose an approach and I choose differently, append the exchange to
`docs/decisions.md` in this format:

**Context → What was proposed → What was decided → Why**

Do not write entries for trivial choices. Only decisions that a future reader
would otherwise question.
```

