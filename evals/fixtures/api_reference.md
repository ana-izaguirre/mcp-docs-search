# API Reference

## Endpoints

All endpoints are prefixed with `/v1`. The service speaks JSON exclusively.
Send `Content-Type: application/json` on every request that carries a body.
Responses are always JSON, including error responses.

## Requests

A valid request requires the `Authorization` header with a bearer token and,
for mutating operations, a JSON body. Unknown fields in the request body
are ignored rather than rejected, which allows the API to evolve without
breaking older clients. Missing required fields produce a 400 response with
a message naming the field.

## Responses

Successful responses carry a 2xx status and the requested resource. List
endpoints return a `data` array and a `next_cursor` string; pass the cursor
back to fetch the next page. When there are no more results, `next_cursor`
is an empty string.

## Errors

Errors return a JSON object with `code`, `message`, and `request_id` fields.
The `code` is a stable string you can match on; the `message` is for humans
and may change. Always log the `request_id` when reporting a bug — it maps
to the server-side log entry.
