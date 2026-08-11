# Logging

## Structured Logs

The service emits JSON logs to stdout. Each line is a single object with
timestamp, level, message, and request ID fields. Structured logging lets
you index and query logs by field instead of parsing text. Avoid printing
sensitive data — there is no redaction, so anything written to the log is
stored verbatim.

## Levels

Log levels follow the standard hierarchy: debug, info, warn, error. A
level includes all levels above it — setting info shows info, warn, and
error messages. The default is info. Use debug only for active debugging;
it writes request and response bodies and can expose credentials.

## Aggregation

Logs are written to stdout, not to a file. A log aggregator reads stdout
and forwards logs to your central store. The service does not manage
retention, rotation, or shipping — that is the aggregator's job. If logs
are not appearing, check the aggregator's connection, not the service.

## Retention

Retention is configured in your log aggregator, not in the service. The
service has no concept of log retention because it never stores logs
locally. Set retention policy where logs are aggregated.
