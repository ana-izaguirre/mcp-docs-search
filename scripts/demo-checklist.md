# Recording the demo GIF

`scripts/demo.tape` already renders the client half of the demo to
`docs/demo.gif`. What is still worth recording is the agent half, which cannot
be scripted; this file has the steps. It needs a real terminal.

## What the GIF has to show

The point is not that a server starts. It is that **an agent answers a question
it could not have answered before, and cites the file it came from.** Three
beats, in order:

1. `mcp-docs-search ./docs --db ./docs.db` — indexing, with the chunk count
2. The agent answering a question about the corpus, showing the heading path
3. The agent following up with `get_document` on its own

Keep it under 30 seconds. Nobody watches more.

## Option A — VHS (deterministic, recommended)

[VHS](https://github.com/charmbracelet/vhs) renders a GIF from a script, so the
recording is reproducible and re-renderable after a UI change.

```bash
# macOS
brew install vhs
# Linux
go install github.com/charmbracelet/vhs@latest   # needs ttyd and ffmpeg

vhs scripts/demo.tape          # writes docs/demo.gif
```

Then link it from the README, right under the `## Demo` heading:

```markdown
![Demo](./docs/demo.gif)
```

`scripts/demo.tape` records the indexing and the smoke client, which is fully
scriptable. For the agent half, see option B.

## Option B — asciinema, for a real agent session

The agent's replies cannot be scripted, so capture a live session:

```bash
brew install asciinema agg          # agg converts the cast to a GIF
asciinema rec docs/demo.cast
#   ... run the session below, then Ctrl-D ...
agg --font-size 16 --theme monokai docs/demo.cast docs/demo.gif
```

Session to run while recording:

```bash
uv run mcp-docs-search ./docs --db ./docs.db --rebuild
opencode                      # opencode.json already registers the server
```

Then ask, in this order:

1. `how does chunking handle headings inside code blocks?`
   — the agent should call `search_docs` and quote the heading path
2. `show me the full decision entry for that`
   — this is where it should reach for `get_document` by itself

If it does not chain the two, do not fake it. Ask a question whose answer needs
the surrounding context and try again; if it still does not, that is a finding
about the tool descriptions, not a recording problem.

## Trimming and size

- Target under 2 MB so it loads on the GitHub page. `agg --fps-cap 10` helps.
- Crop to the terminal; no desktop, no browser chrome, no notifications.
- Use a dark theme with a font size that survives GitHub's scaling — 16pt or
  larger. Text that is unreadable in the README is worse than no GIF.

## Before you commit it

- [ ] The corpus on screen is this repository's `./docs`, not a private folder
- [ ] No API keys, tokens, hostnames or file paths from your machine are visible
- [ ] The GIF lives at `docs/demo.gif` and the README links to it
- [ ] `docs/demo-transcript.md` is refreshed from the same session
