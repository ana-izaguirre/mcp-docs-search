# mcp-docs-search

![CI](https://github.com/ana-izaguirre/mcp-docs-search/actions/workflows/ci.yml/badge.svg)
![Coverage](https://codecov.io/gh/ana-izaguirre/mcp-docs-search/branch/main/graph/badge.svg)
![Python](https://img.shields.io/badge/python-3.12+-blue)
![Dependencies](https://img.shields.io/badge/dependencies-1-brightgreen)

An MCP server that gives AI coding agents keyword search over a folder of
markdown documentation. Built on SQLite FTS5 — one runtime dependency, no
vector database, no API keys, no infrastructure.

## Stack

| | |
|---|---|
| **Language** | Python 3.12 |
| **Index** | SQLite FTS5, from the standard library's `sqlite3` |
| **Protocol** | MCP, via the `mcp` package — the only runtime dependency |
| **Tooling** | `uv`, `pytest`, `mypy --strict`, `ruff` |

No vector database, no embedding API, no service to run. `uv sync` is the whole
setup.

## The problem

Your agent knows the language. It does not know your docs.

Ask it how retries are configured in your own system and it guesses, because
your documentation was never in its training data and pasting the whole folder
into context is neither practical nor cheap.

This server closes that gap: point it at a docs folder, and the agent can search
it — getting back the relevant passages with the file and heading they came from.

## Status

Complete, apart from the demo GIF. The task breakdown lives in
[`docs/tasks.md`](./docs/tasks.md); open work is in
[issues](https://github.com/ana-izaguirre/mcp-docs-search/issues).

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
nothing useful — it waits for a client. `scripts/mcp_smoke.py` *is* that client:
it spawns the server, completes the handshake and calls all three tools.

```bash
uv run python scripts/mcp_smoke.py --db ./docs.db --query "chunking"
```

```
tools advertised: search_docs, list_sources, get_document
decisions.md > Fenced code blocks and headings   (score -4.31)
```

If that prints results, any MCP client will get the same ones. A full session
transcript is in [`docs/demo-transcript.md`](./docs/demo-transcript.md).

## Tools

| Tool | Input | Returns |
|---|---|---|
| `search_docs` | `query`, `limit` (clamped to 1–20) | Matching chunks with content, file path, heading path and rank |
| `list_sources` | — | Indexed files, chunk counts, index date |
| `get_document` | `path` | Full contents of one indexed file |

`get_document` exists because a chunk alone often isn't enough — the agent
frequently needs the surrounding context to answer well.

## How it works

Each markdown section becomes one chunk carrying its full heading path:

```
guide.md > Installation > Configuration
```

That path is what separates this from `grep`. It tells the agent *where* a
match lives, not only *what* matched, so the answer can cite a source. Sections
over ~1500 characters split at paragraph boundaries and keep their heading;
sections under ~100 characters merge forward, so a bare subheading never becomes
a chunk of its own.

The index is a build artifact, not state — the markdown is the source of truth
and the `.db` file is a regenerable projection of it. Build it in CI, ship it in
the image, run any number of read-only instances against identical copies.

FTS5 gives real BM25 ranking with an inverted index, from the standard library,
with nothing to operate.

The full reasoning — chunking rules, the layering, and the trust boundary — is
in [`docs/design.md`](./docs/design.md).

## Retrieval quality

Search is only useful if it returns the right document. The evaluation harness
runs a fixed set of questions against a known corpus and reports how often the
expected source appears in the results.

```
recall@1: 0.30   recall@3: 0.44   MRR: 0.36   (50 queries, 21 documents, 84 chunks)
```

Reproduce it with `uv run python evals/run_evals.py`; CI runs the same command
on every push, so these numbers cannot drift without the build noticing.

**That is a deliberately unflattering number.** The questions are written from
a user's point of view without copying the corpus vocabulary — answer from
memory first, then check which file actually holds the answer. An earlier set
written while reading the corpus scored 0.60/0.87, which measured the
question-writing rather than the retrieval. The lower number is the honest one,
and it is the number that tells you whether this fits: keyword search works
when your agent's queries share vocabulary with your documentation, and gives
out when they do not.

The harness prints the queries it failed, which is the useful part:

```
"I updated something but the api keeps giving me the old values"
  expected caching.md, got rate_limiting.md, permissions.md
"we are being blocked after sending a lot of calls"
  expected rate_limiting.md, got data_model.md, caching.md
```

Every failure has the same shape: the question describes a symptom, the corpus
indexes a vocabulary. Nothing connects "keeps giving me the old values" to a
page that says "stale entries expire on their own" — the words never overlap.
That is the known limit of keyword search, and it is why the number is
published rather than buried: if your agents ask in symptoms, put the symptom
words in your documentation, or expect these misses.

### The number the shipping rule actually uses

Two recall percentages can move without the difference meaning anything. The
harness therefore records a per-question baseline and reports what a change
*did*, not just where it landed:

```
Against baseline: fixed 6, broke 0
  + does the api use jwt or oauth
  + are all endpoints paginated
  ...
  exact binomial p = 0.016 over 6 discordant -> significant
```

Only questions whose outcome flipped carry information, so the verdict is
McNemar's exact test over them. With 50 questions the harness can defend a
change of **5 net fixes (+10 points) or larger**; anything smaller it reports
as indistinguishable from noise, and says so rather than letting a flattering
percentage stand. That resolution is why there are 50 questions and not 25 —
at 25 the floor was +20 points, wide enough that a real improvement could pass
for noise.

Record a new baseline with `uv run python evals/run_evals.py --save-baseline`.

## Demo

Not recorded yet — the one item still open.
[`scripts/demo-checklist.md`](./scripts/demo-checklist.md) has the steps and
`scripts/demo.tape` renders the GIF in one command. A text transcript of a real
session is in [`docs/demo-transcript.md`](./docs/demo-transcript.md) in the
meantime.

## Security

**The index is trusted input.** Everything this server returns is corpus text
handed to a model that is deciding what to do next, so anyone who can write a
file into the indexed folder can put text in front of your agent. Point it at
documentation you control; treat a public wiki or a dependency's vendored docs
the way you would treat any untrusted input to an LLM.

The server does not sanitise document text, deliberately — documentation is full
of commands and instruction-shaped prose, and filtering it would corrupt the
corpus while stopping nobody. Saying where the boundary sits is worth more than
a filter that pretends it isn't there.

Inside that boundary, these are structural rather than filtered:

| | |
|---|---|
| **No path traversal** | The server never touches the filesystem at runtime. `get_document` serves only paths already in the index, so there is no code path from a tool argument to a file read |
| **No SQL injection** | Every statement is parameterised; no query is built by concatenation |
| **No FTS5 operator injection** | Free text is sanitised into literal quoted terms, so `NEAR(`, `*` and `"` match as words |
| **No symlink escape** | Directory symlinks are not followed when walking the corpus |
| **Bounded responses** | `search_docs` clamps `limit` to 1–20; `get_document` caps at 50,000 characters and says when it truncated |
| **stdout is the protocol** | Nothing in the server writes to it, with a test that asserts so |

Full reasoning in [`docs/design.md`](./docs/design.md).

## Scope

This does one thing: keyword search over a folder of markdown, with one runtime
dependency. No embeddings, no vector database, no API keys — not as a staging
post on the way to something bigger, but as the finished shape of the tool.

That is a real ceiling, and the section above measures exactly where it sits.
A corpus whose vocabulary matches how people ask about it searches well here; one
that does not needs semantic retrieval, which this deliberately is not.

## How this was built

Written with an AI coding agent, directed by a written specification rather than
ad-hoc prompting.

- [`AGENTS.md`](./AGENTS.md) — the constraints the agent works under: scope
  boundaries, dependency policy, and the definition of done for a task
- [`SPEC.md`](./SPEC.md) — what gets built
- [`docs/tasks.md`](./docs/tasks.md) — the breakdown, with dependencies
- [`docs/decisions.md`](./docs/decisions.md) — where the agent's proposal was
  overridden, and why
- [`docs/design.md`](./docs/design.md) — the reasoning this README summarises,
  including the trust boundary

The decision log is the interesting file. It records the FTS5 ranking bug that
passed every test while returning the worst results first, and the chunk
ordering that scrambled every document past ten chunks while the suite stayed
green — both found by running the thing, not by testing it harder.
