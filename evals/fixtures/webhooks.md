# Webhooks

## Delivery

Events are delivered as an HTTP POST to the URL registered for the
subscription. A delivery counts as successful when the endpoint answers
with any 2xx status within 10 seconds. Anything else — a timeout, a
redirect, a 3xx or an error status — is treated as a failure.

## Retries

Failed deliveries are retried with exponential backoff at 1, 5, 25 and 125
minutes, then abandoned. Each attempt carries the same event ID, so a
receiver that processes an event twice must deduplicate on that ID.
Delivery is at-least-once, never exactly-once.

## Verifying the Sender

Every request is signed. The `X-Signature` header holds an HMAC-SHA256 of
the raw request body using the subscription's signing secret. Compute the
same HMAC over the body you received and compare with a constant-time
function; comparing with `==` leaks timing information.

## Ordering

Events are not guaranteed to arrive in the order they occurred. Each event
carries a monotonic sequence number, and a receiver that cares about order
must reorder using it rather than trusting arrival time.
