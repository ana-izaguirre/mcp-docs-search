# Metrics

## Overview

The service exposes a `/metrics` endpoint in Prometheus format. Scrape it
at the interval your monitoring stack requires. The endpoint is unauthenticated
and should not be exposed to the public internet.

## Counters and Histograms

Request count, error count, and latency histograms are recorded
automatically for every endpoint. Latency is bucketed into standard
histogram buckets. Custom metrics are not supported — the service exposes
only the built-in set.

## Dashboards

A reference dashboard is provided as a JSON import for Grafana. It shows
request rate, error rate, and p50/p95/p99 latency. The dashboard expects
the metric names emitted by the service; if you rename the Prometheus
job, update the dashboard queries to match.

## Alerts

Alert on error rate above 5% over five minutes and on p99 latency exceeding
two seconds. These thresholds are starting points — adjust them to match
your service level objectives. Alerts are configured in Prometheus, not
in the service.
