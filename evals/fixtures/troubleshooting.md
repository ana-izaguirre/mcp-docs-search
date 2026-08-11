# Troubleshooting

## Connection Errors

A connection error usually means the service cannot reach a downstream
dependency. Check the network policy, DNS resolution, and that the
dependency is accepting connections. The service logs the target host
and the error type at warn level. Retries are handled automatically for
connection failures; if the error persists after the configured retry
count, the request fails with 502.

## Timeouts

A timeout occurs when a downstream dependency does not respond within the
configured limit. The default is 30 seconds. If you see timeouts in the
logs, first check whether the downstream service is healthy and responsive
under load. Increasing the timeout is a stopgap; the real fix is to
address the latency at its source. Timeouts are logged at error level
with the endpoint and duration.

## Debug Logging

When diagnosing an issue, raise the log level to debug temporarily. Debug
logging captures the full request and response, including headers. Remember
to revert to info afterward — debug volume is high and can fill disk. The
change takes effect immediately; no restart needed.

## Common Errors

401 means the token is missing, expired, or has the wrong audience. 403
means the token is valid but lacks the required scope. 500 is an unexpected
internal error — report it with the request ID from the response header.
502 and 504 indicate dependency failures, not bugs in this service.
