# SPEC — mcp-docs-search (Phase 1)

> Implementation specification. Paste into the coding agent as initial context.
> Goal: a small, finished MCP server in Python providing keyword search over a
> folder of markdown. Embeddings are Phase 2 — **do not implement them here.**

---

## 1. What it is

An MCP server that indexes a folder of markdown documentation and exposes a
search tool to the agent. The agent asks in natural language; the server returns
the most relevant chunks with their file path and heading hierarchy.

It does **not** generate answers — the agent already does that. It has **no** UI.
It calls **no** model. It requires **no** API keys.

---

## 2. Core architectural decision

**SQLite with FTS5** as index and store, in a single `.db` file.

The reasons belong in the README, because they are the argument of the project:

- FTS5 ships inside the standard library's `sqlite3` module — **zero infrastructure dependencies**
- It gives BM25 ranking out of the box, which is a real baseline rather than substring matching
- In Phase 2, embeddings are added as one more table in the same file: the
  migration is additive, not a redesign
- A sample `.db` can be published in the repository so anyone can try it without indexing

---

## 3. Exposed tools

| Tool | Input | Output |
|---|---|---|
| `search_docs` | `query: str`, `limit: int = 5` | Chunks with content, document path, heading path and BM25 score |
| `list_sources` | — | Indexed documents, chunk count and index time |
| `get_document` | `path: str` | Full content of one indexed document |

`get_document` exists because the agent often needs the context around a chunk.
Without it, it has to guess.

---

## 4. Ingestion and chunking

- Recursively walks a folder looking for `.md` files
- **Heading-based chunking**: each section (`#`, `##`, `###`) is one chunk
- A section over ~1500 characters splits at paragraph boundaries, keeping its heading
- A section under ~100 characters merges into the next one
- Merging happens **before** splitting; after splitting, chunks are never re-merged
- **Every chunk carries its full heading path**: `"guide.md > Installation > Configuration"`

That heading path is the part that most benefits the agent: it tells it *where*
the match lives, not only *what* matched. It is what separates this from `grep`.

Stored document paths are relative to the indexed root and always use forward
slashes, so the same corpus produces an identical index on Windows and on Linux CI.

**Indexing CLI** (no subcommand — a single command):

```bash
mcp-docs-search ./docs --db ./docs.db
mcp-docs-search ./docs --db ./docs.db --rebuild
```

**Server entry point:**

```bash
mcp-docs-search-server --db ./docs.db
```

---

## 5. Technical constraints

- **Python 3.12.** Type hints on every public function; `mypy --strict` must pass over `src/` and `tests/`.
- **SDK:** the `mcp` package. The server should stay small.
- **No stdout in the server.** stdout is the MCP protocol channel. In `server.py`
  and anything it imports, all logging goes to stderr via the `logging` module.
  The CLI is a separate entry point and does write progress to stdout.
- **Input validation:** `limit` is clamped to 1–20, not rejected. An empty or
  whitespace-only query returns an empty result list, not an error.
- **No filesystem access at runtime.** `get_document` accepts only paths already
  present in the index. The index is the sole source of truth once the server is
  running, so path traversal is structurally impossible rather than filtered.
- **Query sanitising.** Free-text queries are converted to literal FTS5 terms
  before matching, so operator characters (`*`, `"`, `NEAR(`, `OR`) cannot raise
  or trigger a full index scan. This deliberately drops operator support in user
  queries.
- **Actionable errors:** if the database is missing, the message must name the
  command to run, not raise a raw `sqlite3` error. Errors returned to the agent
  must be actionable *by the agent* — it cannot read server logs.
- **Storage isolation.** Only `store.py` knows the storage engine. It raises
  `StoreError`; nothing above it imports `sqlite3`. This is what lets Phase 2 add
  embeddings without touching the server.
- **Dependencies:** only `mcp`. Everything else from the standard library. This
  is a design decision, not a limitation.
- **Packaging:** `pyproject.toml` with `uv`.

---

## 6. Structure

```
src/mcp_docs_search/
  __init__.py
  server.py        # MCP server, tool registration
  cli.py           # indexing command
  ingest.py        # markdown chunking (pure: text in, chunks out)
  store.py         # SQLite FTS5: schema, insert, query
tests/
  test_ingest.py
  test_store.py
  test_cli.py
  test_server.py
evals/
  questions.yaml
  run_evals.py
  fixtures/        # ~20 sample md files
AGENTS.md
README.md
LICENSE
SPEC.md
docs/tasks.md
docs/decisions.md
pyproject.toml
```

`ingest.py` does not touch the filesystem. Reading files and walking directories
belong to the CLI layer, which keeps parsing testable with plain strings.

---

## 7. Evals — the part that differentiates the repository

This is not optional. It is the one thing an ordinary RAG demo does not have.

**`evals/questions.yaml`** — 15–20 entries:

```yaml
- query: "how do I configure retries"
  expected_source: "configuration.md"
- query: "what ports does the service use"
  expected_source: "deployment.md"
```

**`evals/run_evals.py`** — runs each query and reports:

- **recall@1** — the correct document is the first result
- **recall@3** — the correct document is among the top three
- The list of failing queries, so they can be reasoned about

**Output goes in the README**, with the real numbers. Format (values below are
illustrative, not measured):

```
recall@1: 0.65   recall@3: 0.85   (20 queries, chunk size 1500)
```

Publishing an imperfect number is more credible than publishing none. And it
sets up Phase 2: the same table, with embeddings, and the comparison writes
itself.

A known candidate for the question set, found while indexing real documentation:
`merge order` returns nothing while `merge ordering` returns a result. FTS5
matches whole terms, so morphological variation misses.

---

## 8. Tests (pytest)

Tests import from the installed package path, never a bare module name, and use
pytest's `tmp_path` fixture, never `tempfile`.

- Chunking splits correctly on headings and preserves the heading path
- Short sections merge; long sections split; merging runs before splitting
- Headings inside fenced code blocks are not treated as headings
- `search_docs` clamps an out-of-range `limit` at the boundary
- An empty query returns an empty list, not an error
- FTS5 operator characters in a query do not raise
- `get_document` with a path absent from the index returns an actionable message
- A missing database produces an actionable message, not a raw exception
- Reindexing with `--rebuild` leaves no orphan chunks
- Nothing in the server writes to stdout

**Known gap:** tests call entry-point functions directly rather than spawning a
subprocess, for speed and stability. That leaves the wiring uncovered —
`project.scripts`, argument parsing and default paths. Three defects reached
manual testing through this gap. A CI smoke test running the published commands
is the mitigation.

---

## 9. README — required sections

1. **The problem** — the agent does not know your internal documentation. In three lines.
2. **Quick start** — index and connect, with a copyable config block for the MCP client.
3. **Tools** — the table from section 3.
4. **How it works** — heading-based chunking and FTS5, with the reasoning behind each decision.
5. **Retrieval quality** — the eval numbers. **This section is what sets it apart.**
6. **Roadmap** — "Phase 2: embeddings over the same SQLite database, measured against this baseline."
7. **How this was built** — the agent workflow. Links to `AGENTS.md` and `docs/decisions.md`.
8. **Demo** — a GIF of a real session: question to the agent, answer with cited sources.

---

## 10. AGENTS.md

The rules for the agent in this repository:

- Conventions: type hints required, `mypy --strict src/ tests/` must pass
- "Never write to stdout in the server"; the CLI may
- "Only the `mcp` dependency; anything else needs justification"
- "Every new tool needs input validation and a test before implementation"
- "Do not add embeddings, reranking or LLM calls — that is Phase 2"
- "Do not execute commands; do not read repository files unless told to"
- "Do not implement functions belonging to other tasks"
- What must pass before a task is considered done

---

## 11. docs/decisions.md

Format: **context → what the agent proposed → what was decided → why.**

Entries that arise naturally:

- Why FTS5 rather than a vector store from the start
- Why chunking follows headings instead of a fixed-size window
- Why the server does not generate answers
- Why `get_document` exists alongside `search_docs`
- Where the boundary between the server and the store layer sits, and why

This is the section that demonstrates judgement. An AI-generated repository does
not have it.

---

## 12. Definition of done

- [x] The index command works over a real markdown folder
- [x] The three tools respond from a real MCP client
- [ ] `mypy --strict` and `pytest` pass in CI (GitHub Actions)
- [ ] Evals running, with the numbers in the README
- [ ] README with a demo GIF
- [x] AGENTS.md and docs/decisions.md written
- [ ] Published to PyPI (optional, but adds credibility)

**Add nothing else.** No embeddings, no PDFs, no reranking, no UI. Phase 2 is a
separate milestone.