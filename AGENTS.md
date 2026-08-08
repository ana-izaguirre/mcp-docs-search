# mcp-docs-search â€” Setup de OpenCode
---

## Paso 0 â€” Preparar el repo (15 min, una sola vez)

```bash
mkdir mcp-docs-search && cd mcp-docs-search
git init
uv init --package mcp-docs-search
```

Instalar las skills. **Solo estas cuatro** â€” no las 24, que llenan el contexto con cosas de frontend que aquÃ­ no aplican:

```bash
npx skills add addyosmani/agent-skills --skill test-driven-development
npx skills add addyosmani/agent-skills --skill incremental-implementation
npx skills add addyosmani/agent-skills --skill planning-and-task-breakdown
npx skills add addyosmani/agent-skills --skill documentation-and-adrs
```

Guardar `spec-mcp-docs-search-fase1.md` en la raÃ­z como `SPEC.md`, y crear el `AGENTS.md` de la secciÃ³n siguiente.

---

## AGENTS.md â€” pegar tal cual en la raÃ­z del repo

```markdown
# AGENTS.md

## Project

`mcp-docs-search` â€” an MCP server that indexes a folder of markdown documentation and
exposes keyword search to an AI agent. Written in Python.

The full specification lives in `SPEC.md`. Read it before starting any task.

## Scope boundaries â€” do not cross these

This is Phase 1. The following are explicitly **out of scope** and must not be
implemented, suggested, or scaffolded for:

- Embeddings, vector search, or any RAG technique (that is Phase 2)
- Any call to an LLM or external API
- Answer generation â€” this server retrieves, the agent generates
- Web UI, PDF ingestion, incremental reindexing, reranking

If a task seems to require any of these, stop and ask instead of implementing.

## Technical constraints

- Python 3.12. Type hints on every public function. `mypy --strict` must pass.
- Only one runtime dependency: the `mcp` package. Everything else comes from the
  standard library. Adding a dependency requires explicit justification and my
  approval â€” do not add one unilaterally.
- Storage is SQLite with FTS5, from the stdlib `sqlite3` module. Do not introduce
  an ORM, a migration tool, or an external database.
- **Never write to stdout.** stdout is the MCP protocol channel. All logging goes
  to stderr via the `logging` module. A `print()` anywhere in `src/` is a bug.
- Validate tool inputs at the boundary. `limit` is clamped to 1-20. A `path`
  outside the indexed folder is rejected â€” no path traversal.
- Errors returned to the agent must be actionable. "Database not found â€” run
  `mcp-docs-search index ./docs`" is correct. A raw `sqlite3.OperationalError` is not.
- The `chunks` table is FTS5: no column types, no constraints, no external
  indexes. FTS5 maintains its own inverted index.
- FTS5 ranking uses `ORDER BY rank` ascending â€” bm25() returns negative
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

## Definition of done, per task

- [ ] Test written first, fails for the right reason, then passes
- [ ] `mypy --strict src/` passes
- [ ] `pytest` passes, output shown
- [ ] No `print()` in `src/`
- [ ] Committed

## Commands

```bash
uv run pytest              # tests
uv run mypy --strict src/  # types
uv run mcp-docs-search index ./docs --db ./docs.db
uv run python evals/run_evals.py
```

## Decision log

When you propose an approach and I choose differently, append the exchange to
`docs/decisions.md` in this format:

**Context â†’ What was proposed â†’ What was decided â†’ Why**

Do not write entries for trivial choices. Only decisions that a future reader
would otherwise question.
```

---

## Plan de sesiones (45 min cada una)

### SesiÃ³n 1 â€” Plan
```
Read SPEC.md and AGENTS.md. Break Phase 1 into small, verifiable tasks
with acceptance criteria and dependency ordering. Write the result to
docs/tasks.md. Do not write any implementation code yet.
```
Revisa la lista antes de seguir. Si tiene mÃ¡s de 15 tareas, pÃ­dele que las agrupe.

### SesiÃ³n 2 â€” Store
```
Implement task 1 from docs/tasks.md: the SQLite FTS5 store in src/mcp_docs_search/store.py.
Tests first.
```

### SesiÃ³n 3 â€” Chunking
```
Implement the markdown chunking in src/mcp_docs_search/ingest.py. Heading-based, with
the heading path preserved on each chunk. Tests first â€” include the merge and
split edge cases from SPEC.md section 4.
```

### SesiÃ³n 4 â€” CLI de indexado
```
Implement the `mcp-docs-search index` command wiring ingest to store, with --rebuild.
```

### SesiÃ³n 5 â€” Servidor MCP
```
Implement the MCP server in src/mcp_docs_search/server.py with the search_docs tool only.
Remember: nothing to stdout.
```
**AquÃ­ ya funciona de punta a punta.** ConÃ©ctalo a OpenCode y pruÃ©balo tÃº misma.

### SesiÃ³n 6 â€” README y demo
```
Write the README following the required sections in SPEC.md section 9.
Leave the "Retrieval quality" section as a placeholder for now.
```
Graba el GIF tÃº, con una sesiÃ³n real. **Publica el repo aquÃ­**, aunque falten tools.

### SesiÃ³n 7 â€” Evals
```
Implement evals/run_evals.py and the fixtures. Report recall@1 and recall@3.
Run it and put the real numbers in the README.
```

### SesiÃ³n 8 â€” Cierre
```
Implement list_sources and get_document. Then set up GitHub Actions running
pytest and mypy --strict.
```

### SesiÃ³n 9 â€” RevisiÃ³n con contexto limpio
SesiÃ³n **nueva**, sin el historial de las anteriores:
```
Review this repository as a senior engineer would before approving a merge.
Focus on: input validation at boundaries, error messages, anything written to
stdout, and test coverage of the failure paths.
```

---

## Reglas de trabajo con el agente

**Una tarea por sesiÃ³n.** Si le das tres, hace las tres a medias.

**Exige la salida de los tests.** Si dice "los tests pasan" sin pegarlos, pÃ­deselos. Es el error mÃ¡s frecuente y el mÃ¡s caro.

**Cuando lo corrijas, apÃºntalo.** Cada vez que rechaces una propuesta suya, pÃ­dele que aÃ±ada la entrada a `docs/decisions.md`. Ese archivo es tu evidencia de criterio, y se escribe solo si lo pides en el momento.

**Si empieza a irse de alcance** â€”sugiere embeddings, propone aÃ±adir una dependenciaâ€” recuÃ©rdale el `AGENTS.md`. Que se desvÃ­e no es fallo tuyo; corregirlo rÃ¡pido es la habilidad.

---

## Si solo tienes tiempo para tres sesiones

Sesiones 2, 3 y 5, y publicas con un README mÃ­nimo. Un servidor MCP que funciona y estÃ¡ publicado vale mÃ¡s que uno perfecto sin publicar.

