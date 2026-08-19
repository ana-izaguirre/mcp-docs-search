# Architecture

## Components

Three processes make up a deployment: the API server that handles requests,
the worker pool that drains the job queue, and the scheduler that enqueues
recurring work. All three run the same image and are selected by their
start command.

## Request Path

A request arrives at the load balancer, is authenticated at the API server,
checked against permissions, then served either from the response cache or
from the database. Nothing else sits in the path — there is no separate
gateway process to configure or fail.

## Storage

Relational data lives in PostgreSQL. The job queue lives in the same
database rather than a dedicated broker, which trades throughput for one
fewer moving part and lets a job be enqueued in the same transaction as the
data that caused it.

## Why It Is Not Microservices

The components split along runtime shape — request-serving, background
processing, timekeeping — rather than along business domains. Splitting by
domain would multiply the network calls inside a single user action without
making any part independently deployable in practice.
