# Migrations

## Overview

Migrations modify the data model. Each migration is a one-way transformation
applied in sequence. They run automatically on startup; if a migration fails,
the service does not start. Migrations are forward-only — there is no
rollback mechanism.

## Versioning

Every migration carries a version number. The service tracks the current
version in the `schema_migrations` table. On startup it compares the recorded
version to the highest available migration and applies any that are missing.
A migration runs only once; it is never re-applied.

## Writing Migrations

A migration is a function that transforms the current schema into the next
one. It must be idempotent in the sense that running it on an already-migrated
database is a no-op, though in practice it only runs once. Keep migrations
small and focused — one schema change per migration.

## Rollback

There is no automated rollback. To undo a migration you must write a new
migration that reverses the change. Test reversions in a staging environment
before applying them to production.
