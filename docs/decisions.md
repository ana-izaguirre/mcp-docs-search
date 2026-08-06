**Context → What was proposed → What was decided → Why**

**CLI scope creep → Proposed adding list and document commands to the CLI alongside index → Decided CLI has only index, keeping list_sources and get_document as MCP tools only → Reason: delegating to CLI layer adds indirection with no benefit, and the CLI's single responsibility is building the index**