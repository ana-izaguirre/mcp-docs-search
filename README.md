# mcp-docs-search

![CI](https://github.com/ana-izaguirre/mcp-docs-search/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.12+-blue)
![Dependencies](https://img.shields.io/badge/dependencies-1-brightgreen)

An MCP server that gives AI coding agents keyword search over a folder of
markdown documentation. Built on SQLite FTS5 — one runtime dependency, no
vector database, no API keys, no infrastructure.

## The problem

Your agent knows the language. It does not know your docs.

Ask it how retries are configured in your own system and it guesses, because
your documentation was never in its training data and pasting the whole folder
into context is neither practical nor cheap.

This server closes that gap: point it at a docs folder, and the agent can search
it — getting back the relevant passages with the file and heading they came from.

## Status

Phase 1, in progress.

- [x] SQLite FTS5 store — indexing, search, input validation
- [x] Heading-based markdown chunking
- [x] `index` CLI command
- [x] MCP server with `search_docs`, `list_sources`, `get_document`
- [x] Retrieval evaluation harness — numbers below
- [x] Integration tests over the real MCP protocol
- [ ] Demo GIF of a live session

## Quick start

```bash
uv sync
uv run mcp-docs-search ./docs --db ./docs.db
```

Then register the server with your MCP client. The block below is
[OpenCode](https://opencode.ai)'s format, and is already checked in as
`opencode.json`:

```json
{
  "mcp": {
    "docs": {
      "type": "local",
      "command": ["uv", "run", "mcp-docs-search-server", "--db", "./docs.db"],
      "enabled": true
    }
  }
}
```

For Claude Code, the same server registers with:

```bash
claude mcp add docs -- uv run mcp-docs-search-server --db ./docs.db
```

### Check it works before wiring it into an editor

The server speaks MCP over stdin/stdout, so running it in a terminal shows
nothing useful — it waits for a client. `scripts/mcp_smoke.py` *is* that
client: it spawns the server, completes the handshake and calls all three
tools.

```bash
uv run python scripts/mcp_smoke.py --db ./docs.db --query "chunking"
```

```
tools advertised: search_docs, list_sources, get_document

--- search_docs('chunking') ---
  decisions.md > Fenced code blocks and headings  (score -4.31)
    **Context** - Fenced code blocks and headings  **Proposed** - treating any...

--- get_document('decisions.md') ---
  6168 characters returned
```

If that prints results, any MCP client will get the same ones.

## Tools

| Tool | Input | Returns |
|---|---|---|
| `search_docs` | `query`, `limit` (clamped to 1–20) | Matching chunks with content, file path, heading path and rank |
| `list_sources` | — | Indexed files, chunk counts, index date |
| `get_document` | `path` | Full contents of one indexed file |

`get_document` exists because a chunk alone often isn't enough — the agent
frequently needs the surrounding context to answer well.

## How it works

### Chunking follows headings, not a fixed window

Each markdown section becomes one chunk, and every chunk carries its full
heading path:

```
guide.md > Installation > Configuration
```

That path is what makes a result useful to an agent. It tells it *where* the
match lives, not just *what* matched — which is the difference between this and
running `grep`.

Sections over ~1500 characters split at paragraph boundaries, keeping their
heading. Sections under ~100 characters merge into the next one, so a bare
subheading never becomes a chunk of its own.

Verified end to end against the FastAPI documentation: 155 files,
1927 chunks, none skipped. The agent chained `search_docs` into
`get_document` on its own — the behaviour `get_document` was added
for.

### Why SQLite FTS5 instead of a vector database

FTS5 ships inside Python's standard library `sqlite3` module. It gives real
BM25 ranking with an inverted index — not substring matching — and it costs
nothing to run.

That buys three things:

**Zero infrastructure.** Clone, index, done. No Docker, no service to start, no
API key. The barrier to trying this is a single command.

**A measurable baseline.** Adding embeddings without knowing what plain keyword
search already achieves means you can't tell whether they helped. The evaluation
harness measures Phase 1 so Phase 2 has something to beat.

**An additive migration path.** Phase 2 adds a vector table to the same database
file. Nothing gets rewritten.

### The index is a build artifact, not state

The markdown files are the source of truth. The `.db` file is a projection of
them, regenerable at any time.

That changes how it's operated: no backups, no migrations, no corruption
recovery. Build it in CI, ship it inside the container image, and run any number
of read-only instances against identical copies.

```yaml
- run: uv run mcp-docs-search ./docs --db ./docs.db
- run: docker build .
```

## Retrieval quality

Search is only useful if it returns the right document. The evaluation harness
runs a fixed set of questions against a known corpus and reports how often the
expected source appears in the results.

```
recall@1: 0.47   recall@3: 0.67   (15 queries, 10 documents, 40 chunks)
```

Reproduce it with `uv run python evals/run_evals.py`; CI runs the same command
on every push, so these numbers cannot drift without the build noticing.

**Read them with one caveat.** The current question set was written while
looking at the corpus, which biases the wording towards the text it is supposed
to find — so 0.47 and 0.67 flatter the system rather than measuring it. The
questions are being rewritten blind: answer from memory first, then check which
file actually holds the answer. The honest number is expected to be lower, and
will replace this one.

The harness prints the queries it failed, which is the useful part:

```
"request keeps timing out"
  expected troubleshooting.md, got data_model.md, configuration.md
"what does a 401 error mean"
  expected api_reference.md, got troubleshooting.md, authentication.md
```

Both failures are the same shape: the question describes a symptom, the corpus
indexes a vocabulary. Keyword search has no way to connect "keeps timing out"
to a page that says "deadline exceeded". That is the gap Phase 2 has to close,
and now there is a number attached to it.

## Demo

Not recorded yet — this is the one item of Phase 1 still open.
[`scripts/demo-checklist.md`](./scripts/demo-checklist.md) has the steps and
`scripts/demo.tape` renders the GIF in one command. A text transcript of a real
session is in [`docs/demo-transcript.md`](./docs/demo-transcript.md) in the
meantime.

## Roadmap

**Phase 2 — semantic search.** Embeddings stored alongside the FTS5 index in the
same SQLite file, with hybrid retrieval. The evaluation numbers above become the
baseline it has to beat; if it doesn't, it doesn't ship.

## How this was built

Written with an AI coding agent, directed by a written specification rather than
ad-hoc prompting.

- [`AGENTS.md`](./AGENTS.md) — the constraints the agent works under: scope
  boundaries, dependency policy, and the definition of done for a task
- [`SPEC.md`](./SPEC.md) — what gets built
- [`docs/tasks.md`](./docs/tasks.md) — the breakdown, with dependencies
- [`docs/decisions.md`](./docs/decisions.md) — where the agent's proposal was
  overridden, and why

The decision log is the interesting file. It records the FTS5 ranking bug that
passed every test while returning the worst results first, among others.
