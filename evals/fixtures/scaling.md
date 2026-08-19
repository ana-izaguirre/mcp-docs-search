# Scaling

## Horizontal Scaling

The service is stateless and can run as many replicas as needed behind a
load balancer. Session state lives in the database, not in process memory,
so a request may be served by any replica and sticky sessions are not
required.

## Background Workers

Long operations — exports, bulk imports, report generation — are handed to
a queue and processed by worker processes. Workers scale independently of
the API replicas. A queue that grows steadily means workers are
underprovisioned, not that the API is slow.

## Connection Limits

Each replica opens a pool of 20 database connections. The database accepts
500 in total, so beyond 25 replicas the pool size has to come down or the
database will start refusing connections. This ceiling is the first one
most deployments hit.

## What Does Not Scale Horizontally

The scheduler runs on a single elected leader. Running two schedulers
would double every recurring job, so the leader election is not optional
and a deployment with an odd number of nodes is required for it.
