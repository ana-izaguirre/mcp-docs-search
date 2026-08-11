# Configuration

## Server

The service binds to port 8080 by default. Override with the `PORT`
environment variable. When running multiple instances on one host, each
must use a unique port to avoid binding failures.

## Timeouts

The default request timeout is 30 seconds. For endpoints that trigger
long-running jobs — report generation, bulk export — raise the timeout
with the `REQUEST_TIMEOUT` variable. A request that exceeds the timeout
receives a 504 response. Timeouts do not retry automatically; combine
with the retry settings below for resilience.

## Retries

Control retry behaviour with two variables. `RETRY_COUNT` sets the
maximum number of attempts, default 3. `RETRY_BACKOFF` sets the delay
in milliseconds between attempts, default 500. The backoff is linear,
not exponential: each wait is the same length. Retries only apply to
5xx responses and connection errors, never to 4xx client errors.

## Log Levels

Set `LOG_LEVEL` to one of: debug, info, warn, error. The default is
info. Use debug sparingly — it writes the full request and response
body to the log, which is verbose and may expose secrets. Changes to
`LOG_LEVEL` take effect immediately without a restart.
