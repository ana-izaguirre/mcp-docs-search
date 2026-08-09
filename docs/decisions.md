**Context → What was proposed → What was decided → Why**

**CLI scope creep → Proposed adding list and document commands to the CLI alongside index → Decided CLI has only index, keeping list_sources and get_document as MCP tools only → Reason: delegating to CLI layer adds indirection with no benefit, and the CLI's single responsibility is building the index**

**Fenced code blocks and headings → Proposed treating any `# ...` line as a heading → Decided lines inside ```` ``` ````/`~~~` fences are never headings, and a fence only closes with the same char and a run length >= the opener, else it runs to EOF → Reason: code samples are full of `# comments`; mis-chunking them destroys retrieval quality and produces headings the agent can't act on**

**Merge-then-split ordering → Proposed merging short sections and splitting long ones in a single interleaved pass → Decided merge all short sections first, then split long ones; split chunks are never re-merged → Reason: splitting first could leave small orphan chunks that then get merged with the wrong neighbour; the pipeline is deterministic in one direction**

**Heading retained on merge → Proposed dropping the absorbed section's heading when merging → Decided the merged chunk keeps the superior section's heading path and start_line, and the absorbed heading line is kept as literal text inside the chunk → Reason: the heading path tells the agent *where* the text is; erasing it loses the document context that justifies heading-based chunking**

**Last-section merge direction → Proposed always merging a short section into the next one → Decided the last short section merges backward into its predecessor, and a lone short section is kept as-is → Reason: there is no next section at end of file, and forcing a forward merge there would corrupt the final chunk; an only section is left untouched because there is nothing to merge with**

**Thresholds measured on stripped body → Proposed counting heading path and whitespace toward the 100/1500 limits → Decided thresholds are module constants applied to the body after `strip()`, excluding the heading path → Reason: headings are metadata, not content; trailing whitespace and indentation would otherwise skew chunk sizing and split at wrong points**

**Split never inside a paragraph or code block → Proposed splitting long sections at fixed character counts → Decided splits happen only at paragraph boundaries, and an oversized single paragraph or code block is kept whole → Reason: cutting mid-paragraph or mid-code-block produces chunks that are misleading to the agent and break quoted examples**