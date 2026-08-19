# Command Line Reference

## Global Flags

`--config` points at an alternative configuration file. `--verbose` raises
output detail without changing the log level of the service itself.
`--json` makes every command emit machine-readable output instead of the
human-formatted tables used by default.

## Common Commands

`status` reports health, version and uptime. `apply` sends a configuration
file to the running instance and prints what changed. `export` writes the
workspace contents to a directory as files, one per resource.

## Exit Codes

Zero means success. One means the command was used wrongly — a bad flag, a
missing file, a malformed argument. Two means the command was correct but
the operation failed, typically a network or permission problem. Scripts
should distinguish the two: retrying a 1 will never help.

## Shell Completion

`completion bash` and `completion zsh` print a script to source. The
completions are generated from the command tree at build time, so they
never drift from the binary that produced them.
