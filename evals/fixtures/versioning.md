# Versioning and Upgrades

## API Versions

The version is part of the path: `/v1/`, `/v2/`. A version stays available
for at least 12 months after its successor ships, and the deprecation date
is announced when the successor is released, not later.

## What Counts as Breaking

Removing a field, renaming one, narrowing an accepted value, or changing a
status code is breaking and requires a new version. Adding an optional
field or a new endpoint is not, so clients must ignore fields they do not
recognise rather than failing on them.

## Deprecation Signals

A call to a deprecated endpoint still succeeds but returns a `Deprecation`
header carrying the removal date and a `Link` header pointing at the
replacement. Watching for that header in a client's logs is the earliest
warning available.

## Upgrading

Each version ships a migration note listing every breaking change with a
before and after example. There is no automatic translation layer between
versions: running both in parallel during a migration is the supported
path.
