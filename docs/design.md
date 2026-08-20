# Design notes

The reasoning behind the choices the README only summarises. For the decisions
that were argued and overridden during development, see
[`decisions.md`](./decisions.md).

## Chunking follows headings, not a fixed window

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
subheading never becomes a chunk of its own. Merging runs before splitting, and
split chunks are never re-merged, so the same input always produces the same
boundaries.

Headings inside fenced code blocks are not headings. Code samples are full of
`# comments`, and treating them as structure destroys retrieval quality.

Verified end to end against the FastAPI documentation: 155 files, 1927 chunks,
none skipped. The agent chained `search_docs` into `get_document` on its own —
the behaviour `get_document` was added for.

## Why SQLite FTS5 instead of a vector database

FTS5 ships inside Python's standard library `sqlite3` module. It gives real
BM25 ranking with an inverted index — not substring matching — and it costs
nothing to run.

That buys three things:

**Zero infrastructure.** Clone, index, done. No Docker, no service to start, no
API key. The barrier to trying this is a single command.

**A measurable baseline.** Retrieval quality is only an opinion until something
measures it. The evaluation harness puts a number on what plain keyword search
achieves over this corpus, including where it gives out.

## The index is a build artifact, not state

The markdown files are the source of truth. The `.db` file is a projection of
them, regenerable at any time.

That changes how it's operated: no backups, no migrations, no corruption
recovery. Build it in CI, ship it inside the container image, and run any number
of read-only instances against identical copies.

```yaml
- run: uv run mcp-docs-search ./docs --db ./docs.db
- run: docker build .
```

## Layering

Four modules, with one rule each:

| Module | Responsibility | Constraint |
|---|---|---|
| `ingest.py` | Markdown to chunks | Pure. No filesystem, no `store.py` |
| `store.py` | SQLite FTS5 | The only module that imports `sqlite3`; raises `StoreError` |
| `cli.py` | Walk, read, index | The only layer that writes to stdout |
| `server.py` | MCP tools | No filesystem access at runtime; stdout is the protocol |

Nothing above `store.py` knows the storage engine, so the storage engine can
change without the server noticing.

## Trust boundary

The index is trusted input. Everything the server returns is text from the
indexed corpus, handed to a language model that is deciding what to do next, so
anyone who can write a file into the indexed folder can put text in front of the
agent.

Point this at documentation you control. A corpus built from user-submitted
content, a public wiki, or a dependency's vendored docs deserves the same
scrutiny as any untrusted input to an LLM. The server does not sanitise document
text, deliberately: documentation legitimately contains commands and
instruction-shaped prose, and filtering it would corrupt the corpus while
stopping nothing determined.

What the server does guarantee:

- **No filesystem access at runtime.** `get_document` serves only paths already
  in the index, so path traversal is structurally impossible rather than
  filtered
- **No SQL construction.** Every statement is parameterised
- **No FTS5 operator injection.** Free text is sanitised into literal quoted
  terms, so `NEAR(`, `*` and `"` are matched as words
- **No symlink escape.** Directory symlinks are not followed when walking the
  corpus
- **stdout is the protocol.** Nothing in the server writes to it, with a test
  that asserts so
