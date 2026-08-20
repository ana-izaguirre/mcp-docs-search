# Demo transcript

A real session against this repository's own `./docs` folder, captured with
`scripts/mcp_smoke.py`. The GIF in the README shows the same session running;
this is the text of it, so the output stays greppable and reviewable in a diff.

```bash
uv run mcp-docs-search ./docs --db ./docs.db --rebuild
uv run python scripts/mcp_smoke.py --db ./docs.db --query "chunking headings"
```

## 1. Indexing

```console
$ uv run mcp-docs-search ./docs --db ./docs.db --rebuild
Indexed 4 files, 52 chunks, 0 skipped
```

## 2. The client connects and the server advertises its tools

```console
$ uv run python scripts/mcp_smoke.py --db ./docs.db --query "chunking headings"
tools advertised: search_docs, list_sources, get_document
```

## 3. `list_sources` — what the agent can see

```json
{"result": [
  {"path": "decisions.md",       "indexed_at": "2026-08-20T15:48:46+00:00", "chunk_count": 27},
  {"path": "demo-transcript.md", "indexed_at": "2026-08-20T15:48:46+00:00", "chunk_count": 7},
  {"path": "design.md",          "indexed_at": "2026-08-20T15:48:46+00:00", "chunk_count": 6},
  {"path": "tasks.md",           "indexed_at": "2026-08-20T15:48:46+00:00", "chunk_count": 12}
]}
```

## 4. `search_docs("chunking headings")`

```
decisions.md > Decisions > Implementation > Fenced code blocks and headings  (score -4.93)
  **Context** — Fenced code blocks and headings  **Proposed** — treating any
  `# ...` line as a heading  **Decided** — line...

demo-transcript.md > Demo transcript > 4. `search_docs("chunking headings")`  (score -4.90)
  ``` decisions.md > Decisions > Implementation > Fenced code blocks and
  headings   (score -5.58)   **Context** — Fenced c...

demo-transcript.md > Demo transcript > 2. The client connects and the server advertises its tools  (score -4.47)
  ```console $ uv run python scripts/mcp_smoke.py --db ./docs.db --query
  "chunking headings" tools advertised: search_docs...
```

The heading path is the payload. `decisions.md > Decisions > Implementation >
Fenced code blocks and headings` tells the agent exactly where the answer
lives, which a substring match never does. Scores are BM25: more negative is
more relevant, so the first result outranks the rest.

Results two and three are this file matching itself — the transcript lives in
the indexed folder, so it is part of the corpus it documents. Left in rather
than trimmed, because a doctored transcript is worth nothing.

## 5. `get_document("decisions.md")` — the follow-up

```
18370 characters returned
starts: Format: **Context → What was proposed → What was decided → Why.**
        Only decisions a future reader would otherwise question. --- ###
        FTS5 instead of a vector st...
```

Chunks come back in source order. That is a regression test now
(`test_get_document_order_survives_the_protocol`) — ordering used to be
lexicographic on the chunk id, which scrambled every document past ten chunks.

## 6. A path that is not in the index

```
Document not found: 'does-not-exist.md'. Use list_sources to see available documents.
```

Actionable by the agent, which cannot read server logs. Note that the server
never touches the filesystem at runtime: `../../etc/passwd` returns this same
message, because the index is the only source of truth once the server is up.
