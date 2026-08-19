# Client Libraries

## Available Languages

Official clients exist for Python, TypeScript and Go. They wrap the same
HTTP API and add retries, pagination handling and typed responses. A
language without an official client can use the OpenAPI document to
generate one.

## Installing

The Python client is on PyPI as `acme-client`, the TypeScript one on npm as
`@acme/client`, and the Go one is fetched with `go get`. All three follow
semantic versioning and track the API version rather than their own
feature set.

## Automatic Retries

Clients retry idempotent requests up to three times on connection failures
and 5xx responses, with jittered backoff. Non-idempotent requests are never
retried automatically — a duplicated create is worse than a visible error.

## Pagination Helpers

Every list method exposes an iterator that fetches pages transparently.
Iterating consumes pages lazily, so a large result set never loads entirely
into memory unless the caller materialises it.
