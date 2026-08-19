# Testing Against the Service

## Sandbox Environment

A separate sandbox runs the same build as production against a throwaway
database that is reset every night at midnight UTC. Sandbox keys are
prefixed `sk_test_` and cannot be used against production, and production
keys are rejected by the sandbox.

## Seed Data

Every reset loads the same fixture workspace: three users, two projects and
a handful of records with stable identifiers. Tests can rely on those
identifiers existing, which makes assertions readable without a setup step.

## Simulating Failures

Sending the header `X-Simulate: timeout`, `rate_limit` or `server_error`
makes the sandbox produce that condition deliberately. This is the
supported way to exercise error handling — do not test a client's retry
logic by hammering the service until it breaks on its own.

## What Differs From Production

The sandbox runs a single replica with no cache layer, so timing-sensitive
behaviour will not match. It is intended for correctness, never for
performance measurement.
