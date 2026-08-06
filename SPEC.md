# SPEC — docs-mcp (Fase 1)

> Especificación de implementación. Pegar en OpenCode como contexto inicial.
> Objetivo: servidor MCP en Python, pequeño y terminado, con búsqueda por palabras
> clave sobre una carpeta de markdown. Los embeddings son fase 2 — **no implementarlos aquí.**

---

## 1. Qué es

Un servidor MCP que indexa una carpeta de documentación en markdown y expone al agente
una herramienta de búsqueda. El agente pregunta en lenguaje natural, el servidor devuelve
los fragmentos más relevantes con su ruta de archivo y su jerarquía de encabezados.

**No** genera respuestas — de eso ya se encarga el agente. **No** tiene UI. **No** llama
a ningún modelo. **No** requiere claves de API.

---

## 2. Decisión de arquitectura central

**SQLite con FTS5** como índice y almacén, en un único archivo `.db`.

Motivos, y van al README porque son el argumento del proyecto:

- FTS5 viene en el módulo `sqlite3` de la librería estándar — **cero dependencias de infraestructura**
- Da ranking BM25 de fábrica, que es un baseline real, no una búsqueda por subcadena
- En la fase 2, los embeddings se añaden como una tabla más en el mismo archivo: la
  migración es aditiva, no un rediseño
- Se puede publicar el `.db` de ejemplo en el repo para que cualquiera pruebe sin indexar

---

## 3. Herramientas expuestas

| Tool | Entrada | Salida |
|---|---|---|
| `search_docs` | `query: str`, `limit: int = 5` | fragmentos con texto, ruta, jerarquía de encabezados y score |
| `list_sources` | — | archivos indexados, nº de fragmentos y fecha de indexado |
| `get_document` | `path: str` | contenido completo de un archivo indexado |

`get_document` existe porque el agente a menudo necesita el contexto alrededor del
fragmento. Sin esto, tiene que adivinar.

---

## 4. Ingesta y chunking

- Recorre recursivamente una carpeta buscando `.md` y `.mdx`
- **Chunking por encabezados**: cada sección (`#`, `##`, `###`) es un fragmento
- Si una sección supera ~1500 caracteres, se parte por párrafos manteniendo el encabezado
- Si una sección baja de ~100 caracteres, se fusiona con la siguiente
- **Cada fragmento guarda su ruta de encabezados completa**: `"guia.md > Instalación > Configuración"`

Esa ruta de encabezados es la parte que más valor aporta al agente: le dice *dónde* está
lo que encontró, no solo *qué* encontró. Es lo que separa esto de un `grep`.

**CLI de indexado:**
```bash
docs-mcp index ./docs --db ./docs.db
docs-mcp index ./docs --db ./docs.db --rebuild
```

---

## 5. Restricciones técnicas

- **Python 3.11+.** Type hints en todas las funciones públicas; `mypy` en modo estricto debe pasar.
- **SDK:** paquete `mcp` (FastMCP). El servidor no debería pasar de ~80 líneas.
- **Sin logs a stdout.** stdout es el canal del protocolo MCP. Todo logging va a stderr con el módulo `logging`.
- **Validación de entradas:** `limit` acotado a 1-20. Un `path` fuera de la carpeta indexada se rechaza — nada de path traversal.
- **Errores accionables:** si la base de datos no existe, el mensaje debe decir qué comando ejecutar, no lanzar un `sqlite3.OperationalError` crudo.
- **Dependencias:** solo `mcp`. Todo lo demás de la librería estándar. Es una decisión de diseño, no una limitación.
- **Empaquetado:** `pyproject.toml` con `uv`. Instalable vía `uvx docs-mcp`.

---

## 6. Estructura

```
src/docs_mcp/
  __init__.py
  server.py        # servidor MCP, registro de tools
  cli.py           # comando de indexado
  ingest.py        # recorrido de ficheros + chunking
  store.py         # SQLite FTS5: esquema, insert, query
tests/
  test_chunking.py
  test_store.py
  test_tools.py
evals/
  questions.yaml
  run_evals.py
  fixtures/        # ~20 ficheros md de ejemplo
AGENTS.md
README.md
docs/decisions.md
pyproject.toml
```

---

## 7. Evals — la parte que diferencia el repo

Esto no es opcional. Es lo único que un demo de RAG normal no tiene.

**`evals/questions.yaml`** — 15-20 entradas:
```yaml
- query: "how do I configure retries"
  expected_source: "configuration.md"
- query: "what ports does the service use"
  expected_source: "deployment.md"
```

**`evals/run_evals.py`** — ejecuta cada consulta e informa:
- **recall@1** — el documento correcto es el primer resultado
- **recall@3** — el documento correcto está entre los tres primeros
- Lista de las consultas fallidas, para poder razonarlas

**Salida en el README**, con los números reales:
```
recall@1: 0.65   recall@3: 0.85   (20 queries, chunk size 1500)
```

Publicar un número imperfecto es más creíble que no publicar ninguno. Y deja el terreno
listo para la fase 2: la misma tabla, con embeddings, y la comparación se escribe sola.

---

## 8. Tests (pytest)

- Chunking parte correctamente por encabezados y conserva la ruta de encabezados
- Secciones cortas se fusionan; secciones largas se parten
- `search_docs` con `limit` fuera de rango se rechaza en el borde
- `get_document` con un path fuera de la carpeta indexada se rechaza
- Base de datos ausente → mensaje accionable, no excepción cruda
- Reindexar con `--rebuild` no deja fragmentos huérfanos

---

## 9. README — secciones requeridas

1. **The problem** — el agente no conoce tu documentación interna. En tres líneas.
2. **Quick start** — indexar y conectar, con bloque de config copiable para el cliente MCP.
3. **Tools** — la tabla de la sección 3.
4. **How it works** — chunking por encabezados y FTS5, con el porqué de cada decisión.
5. **Retrieval quality** — los números de los evals. **Esta sección es la que te distingue.**
6. **Roadmap** — "Fase 2: embeddings sobre la misma base SQLite, con comparación medida contra este baseline."
7. **How this was built** — el flujo con agente. Enlace a `AGENTS.md` y `docs/decisions.md`.
8. **Demo** — GIF de una sesión real: pregunta al agente, respuesta con fuentes citadas.

---

## 10. AGENTS.md

Las reglas para el agente en este repo:

- Convenciones: type hints obligatorios, `mypy --strict` debe pasar
- "Nunca escribir a stdout"
- "Solo la dependencia `mcp`; cualquier otra hay que justificarla"
- "Toda tool nueva necesita validación de entrada y un test antes de la implementación"
- "No añadir embeddings, reranking ni llamadas a LLM — eso es fase 2"
- Cómo correr tests y evals, y qué debe pasar antes de dar una tarea por terminada

---

## 11. docs/decisions.md

Formato: **contexto → qué propuso el agente → qué decidiste → por qué.**

Entradas que van a surgir de forma natural:

- Por qué FTS5 y no un vector store desde el principio
- Por qué se chunkea por encabezados en vez de por ventana de tamaño fijo
- Por qué el servidor no genera respuestas
- Por qué existe `get_document` además de `search_docs`

Esta es la sección que demuestra criterio. Un repo generado por IA no la tiene.

---

## 12. Definición de "terminado"

- [ ] `docs-mcp index` funciona sobre una carpeta real de markdown
- [ ] Las 3 tools responden desde un cliente MCP real
- [ ] `mypy --strict` y `pytest` pasan en CI (GitHub Actions)
- [ ] Evals ejecutándose, con los números en el README
- [ ] README con GIF de demo
- [ ] AGENTS.md y docs/decisions.md escritos
- [ ] Publicado en PyPI (opcional, pero sube mucho la credibilidad)

**No añadir nada más.** Ni embeddings, ni PDFs, ni reranking, ni UI. Fase 2 es otro hito.
