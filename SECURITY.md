# Security policy

## Reporting a vulnerability

Report privately through GitHub's [Security
advisories](https://github.com/ana-izaguirre/mcp-docs-search/security/advisories/new)
form. It is the only channel — please do not open a public issue for something
exploitable.

What helps: the commit or version, what an attacker gains, and the smallest
reproduction you have. A failing command is worth more than a description.

What to expect: an acknowledgement within a week, and a fix or a decision with
reasons within a month. This is a personal project, not a funded one — if a
fix is going to take longer, you will be told that rather than left waiting.

## Supported versions

The project is pre-1.0 and only `main` is supported. There are no maintained
release branches; fixes land on `main`.

## Scope

### The index is trusted input

Everything this server returns is text from the indexed corpus, handed to a
language model that is deciding what to do next. **A document containing
instructions aimed at the agent is returned verbatim, by design.** Document text
is not sanitised, because any filter accurate enough to catch a real injection
would also destroy legitimate documentation — install guides are made of
`curl … | sh` and runbooks are written in the imperative.

Point this at documentation you control. A report that indexed content reaches
the agent unfiltered describes intended behaviour, and
[`docs/design.md`](./docs/design.md) explains the reasoning. A report showing a
way *around* the controls below is a vulnerability.

### In scope

- Reaching a file outside the indexed corpus through any tool argument
- Executing SQL or FTS5 syntax through a query
- Escaping the corpus through symlinks, path encoding or filename tricks
- Any input that crashes the server, hangs it, or makes it consume unbounded
  memory or CPU
- Anything the server writes to stdout, which would corrupt the MCP protocol
  channel
- Credentials or host paths leaking into tool responses or logs

### Out of scope

- Prompt injection through indexed document content (see above)
- Vulnerabilities in the `mcp` package or in your MCP client — report those
  upstream
- What the agent does with a returned document; the sandbox around the agent is
  the client's responsibility
- The size of a `get_document` response, which is capped and documented

## What the server guarantees

These are structural rather than filtered, and each has a test:

| | |
|---|---|
| No runtime filesystem access | `get_document` serves only paths already in the index |
| No SQL construction | Every statement is parameterised |
| No FTS5 operator injection | Free text becomes literal quoted terms |
| No symlink escape | Directory symlinks are not followed when walking |
| Bounded responses | `limit` clamped 1–20; documents capped at 50,000 characters |
| stdout reserved | Nothing in the server writes to it |
