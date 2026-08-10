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