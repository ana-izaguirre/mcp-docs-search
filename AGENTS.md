# docs-mcp — Setup de OpenCode

> Acompaña a `spec-docs-mcp-fase1.md`. Ese archivo dice **qué** construir; este dice **cómo** trabajarlo con el agente.

---

## Paso 0 — Preparar el repo (15 min, una sola vez)

```bash
mkdir docs-mcp && cd docs-mcp
git init
uv init --package docs-mcp
```

Instalar las skills. **Solo estas cuatro** — no las 24, que llenan el contexto con cosas de frontend que aquí no aplican:

```bash
npx skills add addyosmani/agent-skills --skill test-driven-development
npx skills add addyosmani/agent-skills --skill incremental-implementation
npx skills add addyosmani/agent-skills --skill planning-and-task-breakdown
npx skills add addyosmani/agent-skills --skill documentation-and-adrs
```

Guardar `spec-docs-mcp-fase1.md` en la raíz como `SPEC.md`, y crear el `AGENTS.md` de la sección siguiente.

---

## AGENTS.md — pegar tal cual en la raíz del repo

```markdown
# AGENTS.md

## Project

`docs-mcp` — an MCP server that indexes a folder of markdown documentation and
exposes keyword search to an AI agent. Written in Python.

The full specification lives in `SPEC.md`. Read it before starting any task.

## Scope boundaries — do not cross these

This is Phase 1. The following are explicitly **out of scope** and must not be
implemented, suggested, or scaffolded for:

- Embeddings, vector search, or any RAG technique (that is Phase 2)
- Any call to an LLM or external API
- Answer generation — this server retrieves, the agent generates
- Web UI, PDF ingestion, incremental reindexing, reranking

If a task seems to require any of these, stop and ask instead of implementing.

## Technical constraints

- Python 3.11+. Type hints on every public function. `mypy --strict` must pass.
- Only one runtime dependency: the `mcp` package. Everything else comes from the
  standard library. Adding a dependency requires explicit justification and my
  approval — do not add one unilaterally.
- Storage is SQLite with FTS5, from the stdlib `sqlite3` module. Do not introduce
  an ORM, a migration tool, or an external database.
- **Never write to stdout.** stdout is the MCP protocol channel. All logging goes
  to stderr via the `logging` module. A `print()` anywhere in `src/` is a bug.
- Validate tool inputs at the boundary. `limit` is clamped to 1-20. A `path`
  outside the indexed folder is rejected — no path traversal.
- Errors returned to the agent must be actionable. "Database not found — run
  `docs-mcp index ./docs`" is correct. A raw `sqlite3.OperationalError` is not.

## Workflow

- Work in thin vertical slices. One tool or one module per task, not three at once.
- Tests before implementation. A task is not started until its test exists and fails.
- Commit after each task passes. Small commits, present-tense messages.
- Never mark a task done without showing the actual test output. "Should work" is
  not evidence.

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
uv run docs-mcp index ./docs --db ./docs.db
uv run python evals/run_evals.py
```

## Decision log

When you propose an approach and I choose differently, append the exchange to
`docs/decisions.md` in this format:

**Context → What was proposed → What was decided → Why**

Do not write entries for trivial choices. Only decisions that a future reader
would otherwise question.
```

---

## Plan de sesiones (45 min cada una)

### Sesión 1 — Plan
```
Read SPEC.md and AGENTS.md. Break Phase 1 into small, verifiable tasks
with acceptance criteria and dependency ordering. Write the result to
docs/tasks.md. Do not write any implementation code yet.
```
Revisa la lista antes de seguir. Si tiene más de 15 tareas, pídele que las agrupe.

### Sesión 2 — Store
```
Implement task 1 from docs/tasks.md: the SQLite FTS5 store in src/docs_mcp/store.py.
Tests first.
```

### Sesión 3 — Chunking
```
Implement the markdown chunking in src/docs_mcp/ingest.py. Heading-based, with
the heading path preserved on each chunk. Tests first — include the merge and
split edge cases from SPEC.md section 4.
```

### Sesión 4 — CLI de indexado
```
Implement the `docs-mcp index` command wiring ingest to store, with --rebuild.
```

### Sesión 5 — Servidor MCP
```
Implement the MCP server in src/docs_mcp/server.py with the search_docs tool only.
Remember: nothing to stdout.
```
**Aquí ya funciona de punta a punta.** Conéctalo a OpenCode y pruébalo tú misma.

### Sesión 6 — README y demo
```
Write the README following the required sections in SPEC.md section 9.
Leave the "Retrieval quality" section as a placeholder for now.
```
Graba el GIF tú, con una sesión real. **Publica el repo aquí**, aunque falten tools.

### Sesión 7 — Evals
```
Implement evals/run_evals.py and the fixtures. Report recall@1 and recall@3.
Run it and put the real numbers in the README.
```

### Sesión 8 — Cierre
```
Implement list_sources and get_document. Then set up GitHub Actions running
pytest and mypy --strict.
```

### Sesión 9 — Revisión con contexto limpio
Sesión **nueva**, sin el historial de las anteriores:
```
Review this repository as a senior engineer would before approving a merge.
Focus on: input validation at boundaries, error messages, anything written to
stdout, and test coverage of the failure paths.
```

---

## Reglas de trabajo con el agente

**Una tarea por sesión.** Si le das tres, hace las tres a medias.

**Exige la salida de los tests.** Si dice "los tests pasan" sin pegarlos, pídeselos. Es el error más frecuente y el más caro.

**Cuando lo corrijas, apúntalo.** Cada vez que rechaces una propuesta suya, pídele que añada la entrada a `docs/decisions.md`. Ese archivo es tu evidencia de criterio, y se escribe solo si lo pides en el momento.

**Si empieza a irse de alcance** —sugiere embeddings, propone añadir una dependencia— recuérdale el `AGENTS.md`. Que se desvíe no es fallo tuyo; corregirlo rápido es la habilidad.

---

## Si solo tienes tiempo para tres sesiones

Sesiones 2, 3 y 5, y publicas con un README mínimo. Un servidor MCP que funciona y está publicado vale más que uno perfecto sin publicar.
