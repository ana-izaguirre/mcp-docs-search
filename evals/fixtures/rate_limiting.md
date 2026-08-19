# Rate Limiting

## Quotas

Each API key is allowed 1000 requests per minute, measured in a sliding
window rather than a fixed one, so a burst at the boundary cannot double
the effective allowance. Quotas are per key, not per IP address — running
the same key from several machines shares one budget.

## Exceeding the Limit

A request over the quota is rejected with status 429 and a `Retry-After`
header giving the whole seconds to wait. The body names which quota was
exceeded. Rejected requests do not count against the quota themselves, so
a client that retries politely cannot dig itself deeper.

## Headers on Every Response

`X-RateLimit-Limit`, `X-RateLimit-Remaining` and `X-RateLimit-Reset` are
returned on successful responses too, so a client can slow down before it
is refused rather than after.

## Raising a Limit

Limits are set per key in the dashboard. There is no endpoint to change
them programmatically, deliberately: a client that can raise its own
ceiling is not rate limited.
