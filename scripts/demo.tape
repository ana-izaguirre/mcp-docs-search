# VHS tape for the indexing + live-server half of the demo.
#   vhs scripts/demo.tape   ->   docs/demo.gif
# The agent half of the demo cannot be scripted; see scripts/demo-checklist.md.

Output docs/demo.gif

Set Shell bash
Set FontSize 16
Set Width 1200
Set Height 720
Set Theme "Catppuccin Mocha"
Set Padding 20
Set TypingSpeed 45ms

Type "# 1. index a folder of markdown"
Enter
Sleep 800ms
Type "uv run mcp-docs-search ./docs --db ./docs.db --rebuild"
Enter
Sleep 3s

Type "clear"
Enter
Sleep 300ms

Type "# 2. talk to the live MCP server, as a client would"
Enter
Sleep 800ms
Type "uv run python scripts/mcp_smoke.py --db ./docs.db --query 'chunking headings'"
Enter
Sleep 4500ms

Type "# the unknown path above is deliberate: an error the agent can act on, not a crash"
Enter
Sleep 2s

Type "# and every result carries the file and heading path it came from"
Enter
Sleep 3s
