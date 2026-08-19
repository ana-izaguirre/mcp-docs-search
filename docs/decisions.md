# Decisions

Format: **Context → What was proposed → What was decided → Why.**
Only decisions a future reader would otherwise question.

---

## Foundational

### FTS5 instead of a vector store

**Context** — The obvious build for "search over documentation" in 2025 is
embeddings in a vector database. The project deliberately does not start there.

**Proposed** — Embed the chunks and store the vectors in a dedicated vector
database, so semantic search works from day one.

**Decided** — SQLite FTS5 with BM25 ranking for Phase 1, in a single `.db`
file. Embeddings become one more table in the same file in Phase 2.

**Why** — Three reasons, in order of weight. First, it costs nothing to run:
FTS5 ships inside the standard library's `sqlite3` module, so there is no
service, no Docker, no API key, and trying the project is one command. Second,
it produces a measurable baseline — adding embeddings without knowing what
plain keyword search already achieves makes it impossible to say whether they
helped. Third, the migration is additive rather than a redesign, because the
vector table lands in the same file behind the same `store.py` boundary.

### Heading-based chunking instead of a fixed-size window

**Context** — Chunking strategy decides what a search result looks like to the
agent.

**Proposed** — Fixed-size windows with overlap, the standard RAG default.

**Decided** — Each markdown section is one chunk, carrying its full heading
path (`guide.md > Installation > Configuration`). Oversized sections split at
paragraph boundaries and keep the heading; undersized ones merge forward.

**Why** — A fixed window cuts mid-sentence and produces chunks with no
provenance. The heading path tells the agent *where* a match lives, not only
*what* matched — that is the whole difference between this and `grep`, and it
is what makes a result quotable in an answer. Markdown already carries the
document's structure; ignoring it to impose a character count throws away
information the format hands over for free.

### The server retrieves, it does not generate

**Context** — An MCP server could answer the question itself by calling a model
with the retrieved passages.

**Proposed** — Add an `ask_docs` tool that returns a written answer.

**Decided** — The server returns passages only. No LLM call, no API key, no
answer generation.

**Why** — The agent on the other end of the protocol is already a language
model, and a better one than anything this server would call. Generating here
would mean paying twice, adding a key and a network dependency to a tool whose
entire pitch is that it has neither, and losing the citations — the agent needs
the passage and its source to attribute the answer, not a paraphrase of it.

### `get_document` exists alongside `search_docs`

**Context** — `search_docs` returns the matching chunk. Watching a real session
showed the agent immediately wanting the text around it.

**Proposed** — Return larger chunks, or include neighbouring chunks in every
search result.

**Decided** — Keep chunks tight for ranking quality and add a second tool that
returns one whole indexed document.

**Why** — The two needs pull in opposite directions: precise retrieval wants
small chunks, answering wants surrounding context. Inflating every result to
serve the second need degrades the first and wastes the agent's context on
passages it did not ask for. A separate tool lets the agent decide when it
needs the full file — and in the FastAPI trial it chained the two on its own,
which is the behaviour the tool was added for.

### TOML for the eval question set, not YAML

**Context** — SPEC section 7 specifies `evals/questions.yaml`.

**Proposed** — Use YAML as specified, adding `pyyaml` as a dependency.

**Decided** — `evals/questions.toml`, parsed with the standard library's
`tomllib`.

**Why** — The dependency policy allows exactly one runtime dependency, and the
argument of the project is that it needs no infrastructure. Adding a parser
dependency to read fifteen question-and-answer pairs would contradict that for
no gain. The format is an implementation detail of the harness; the SPEC's
intent — a plain-text, hand-editable question set in version control — is
preserved.

---

## Implementation

### CLI scope creep

**Context** — CLI scope creep

**Proposed** — adding list and document commands to the CLI alongside index

**Decided** — CLI has only index, keeping list_sources and get_document as MCP tools only

**Why** — delegating to CLI layer adds indirection with no benefit, and the CLI's single responsibility is building the index

### Fenced code blocks and headings

**Context** — Fenced code blocks and headings

**Proposed** — treating any `# ...` line as a heading

**Decided** — lines inside ` ``` ` / `~~~` fences are never headings, and a fence only closes with the same char and a run length >= the opener, else it runs to EOF

**Why** — code samples are full of `# comments`; mis-chunking them destroys retrieval quality and produces headings the agent can't act on

### Merge-then-split ordering

**Context** — Merge-then-split ordering

**Proposed** — merging short sections and splitting long ones in a single interleaved pass

**Decided** — merge all short sections first, then split long ones; split chunks are never re-merged

**Why** — splitting first could leave small orphan chunks that then get merged with the wrong neighbour; the pipeline is deterministic in one direction

### Last-section merge direction

**Context** — Last-section merge direction

**Proposed** — always merging a short section into the next one

**Decided** — the last short section merges backward into its predecessor, and a lone short section is kept as-is

**Why** — there is no next section at end of file, and forcing a forward merge there would corrupt the final chunk; an only section is left untouched because there is nothing to merge with

### Thresholds measured on stripped body

**Context** — Thresholds measured on stripped body

**Proposed** — counting heading path and whitespace toward the 100/1500 limits

**Decided** — thresholds are module constants applied to the body after `strip()`, excluding the heading path

**Why** — headings are metadata, not content; trailing whitespace and indentation would otherwise skew chunk sizing and split at wrong points

### Split never inside a paragraph or code block

**Context** — Split never inside a paragraph or code block

**Proposed** — splitting long sections at fixed character counts

**Decided** — splits happen only at paragraph boundaries, and an oversized single paragraph or code block is kept whole

**Why** — cutting mid-paragraph or mid-code-block produces chunks that are misleading to the agent and break quoted examples

### Merge before split

**Context** — Merge before split

**Proposed** — interleaving merge and split passes

**Decided** — short sections are merged first, then long sections are split; after splitting, chunks are never re-merged

**Why** — splitting first creates pieces that the merge pass would then rejoin, producing different chunk boundaries for the same input

### Identity of a merged chunk

**Context** — Identity of a merged chunk

**Proposed** — dropping the absorbed section's metadata when merging

**Decided** — a merged chunk keeps the heading_path, level and start_line of the UPPER section; the absorbed section's heading line is preserved as body text so its title stays searchable but does not enter heading_path; a trailing short section with no following section merges backwards

**Why** — the agent needs to know *where* text came from; losing the superior section's identity on merge breaks source attribution

### ingest.py does not touch the filesystem

**Context** — ingest.py does not touch the filesystem

**Proposed** — having chunk_markdown read files directly

**Decided** — chunk_markdown receives already-read text and returns chunks; reading files and walking directories belong to the CLI layer

**Why** — keeps parsing testable with plain strings and decouples it from persistence

### Silent content loss during the content-model refactor

**Context** — Silent content loss during the content-model refactor

**Proposed** — changing _Section.content from str to list[tuple[int, str]] so split pieces could carry a real start_line

**Decided** — _split_sections stopped flushing its accumulated line buffer into the section when closing it, copying the still-empty cur.content instead; every merged section lost its body; no exception, no failing type check — content silently absent from the index

**Why** — Detected by a test written before implementation that asserted the merged chunk's TEXT, not only its heading_path, level and start_line; those three assertions passed while the body was being dropped. Learning: verifying a chunk's identity is not the same as verifying its content; assert both.

### Strip attr_list anchors from heading paths

**Context** — Indexing the FastAPI documentation (155 files, 1927 chunks)
produced heading paths like `_llm-test.md > Quotes { #quotes }`. The
`{ #anchor }` suffix is MkDocs `attr_list` syntax, an extension outside
CommonMark, used to give a heading a stable anchor id.

**Proposed** — Leave heading text verbatim, since `attr_list` is not part of
the markdown standard this parser targets.

**Decided** — Strip a trailing brace block from the heading text before
building heading_path. Only a block at the very end of the heading line;
braces appearing mid-title are preserved.

**Why** — heading_path is the value the MCP server returns to the agent, and
the whole justification for heading-based chunking is that this path tells
the agent *where* a result lives. Anchor syntax is noise in that channel.
MkDocs is common enough in Python documentation that ignoring it would
degrade the primary output on a large share of realistic corpora.

**Found by** — Indexing a real third-party corpus rather than the project's
own docs. The project's two markdown files never exercised this path.

### Nobody owned the documents table

**Context** — The `documents` table was created by the schema but nothing ever inserted into it. Indexing produced 40 chunks and 0 documents, so list_sources returned an empty list and every eval query failed.

**Proposed** — Task 1 built the store, task 3 built the CLI. Each specification had a closed scope and neither claimed ownership of the seam between them.

**Decided** — store.py exposes the insert; cli.py calls it once per indexed file, in the same transaction path as the chunk inserts.

**Why** — Found by the eval harness, the first thing to exercise the full path: index for real, then query for real. Closed-scope task decomposition keeps an agent from overreaching, but it leaves gaps at the seams. Per-layer tests do not cover them; at least one test must cross the whole system.

### Chunk ordering must not rely on the chunk id

**Context** — `get_document` reconstructs a document by concatenating its
chunks. `store.get_chunks` ordered by `chunk_id`, which the CLI builds as
`"{file_index}_{chunk_index}"`. FTS5 stores columns as text, so the sort was
lexicographic: `0_10` landed between `0_1` and `0_2`. Every document with more
than ten chunks came back scrambled — including the FastAPI corpus the README
cites, and silently, since the text was all present.

**Proposed** — Zero-pad the chunk id (`0_000010`), a one-line change that makes
the existing lexicographic sort produce the right order.

**Decided** — Store the position as its own `chunk_index` column, `UNINDEXED`
in the FTS5 table, and order by `CAST(chunk_index AS INTEGER)`.

**Why** — Padding hides ordering inside a string whose format nothing enforces;
the next person to touch the id format reintroduces the bug with no test to
catch it. A dedicated column makes the ordering a property of the data, states
the intent in the schema, and is what Phase 2 will need anyway when chunks
arrive from more than one writer. `ORDER BY rowid` would also work today, but
couples document order to a storage implementation detail.

**Found by** — Not by the unit tests. `test_get_chunks_ordered_by_chunk_id`
passed throughout, because its fixture used two chunks. It took indexing a real
folder and reading the output. Learning: fixtures that stay under ten items
cannot see an ordering defect that begins at eleven.

### The seam between the CLI and the store needs its own tests

**Context** — Two defects — the `documents` table nobody populated, and the
chunk ordering above — both lived in the gap between two correctly implemented
modules, and both survived a green test suite.

**Proposed** — Add more unit tests per module.

**Decided** — Add `tests/test_integration.py`, which runs the published console
scripts as subprocesses and drives the server over a real stdio MCP session,
and require at least one whole-system test per feature.

**Why** — More per-layer tests would not have caught either defect; both layers
were right in isolation. SPEC section 8 already names this gap and calls a CI
smoke test the mitigation, but a smoke test only proves the process starts. The
tests that matter are the ones that index a real folder and then read it back
through the real protocol, because that is the path the user's agent takes.

### Punctuation must be stripped before FTS5 matching

**Context** — A hand-written evaluation question containing a comma —
"I call an endpoint and it hangs forever, is there a timeout" — raised
`fts5: syntax error near ","`. `sanitise_query` split on whitespace and
quoted each token, but the comma still broke the FTS5 parser inside the
quotes.

**Proposed** — Quoting alone was assumed sufficient to make operator
characters inert.

**Decided** — Each token is stripped of characters FTS5 treats as syntax
before quoting. Alphanumerics and intra-word hyphen, underscore and dot
are kept; everything else is dropped. Tokens that become empty are
discarded.

**Why** — Every query test and every generated evaluation question used
text without punctuation. The first question written the way a person
would actually write it broke the engine. The eval corpus does not only
measure retrieval quality; it exercises input paths that unit tests do
not represent.

**Found by** — The evaluation harness was written to mirror real user input, not
a contrived search API. Once a natural-language question included punctuation,
FTS5 exposed the weakness immediately.
