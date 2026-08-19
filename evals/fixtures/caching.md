# Caching

## Response Cache

Read endpoints are cached in memory for 60 seconds by default. The cache
key is the full request path plus the authenticated tenant, so two tenants
never share an entry. Write endpoints are never cached. A cached response
carries an `X-Cache: HIT` header so you can tell where an answer came from
without enabling debug logging.

## Invalidation

Entries expire on their own; there is no manual purge endpoint. A write to
a resource drops every cached entry whose key starts with that resource's
path, which means a single update can clear a large range of list queries.
This is intentional: stale list results are the most common source of
confusing behaviour after an update.

## Tuning the TTL

`cache_ttl_seconds` accepts any value from 0 to 3600. Setting it to 0
disables the cache entirely without removing the header, so `X-Cache` still
reports `MISS` on every request. Raising it above a few minutes is rarely
worth it — the hit rate flattens quickly while the staleness window grows
linearly.

## What Is Not Cached

Authentication decisions, permission checks, and anything returning a 4xx
or 5xx status are never stored. Errors are cheap to recompute and caching
them turns a transient failure into a sticky one.
