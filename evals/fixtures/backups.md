# Backups and Restore

## Snapshots

A full snapshot is taken every 24 hours at 03:00 UTC and kept for 30 days.
Snapshots are consistent: they are taken from a read replica that is
paused for the duration, so a snapshot never contains a half-written
transaction.

## Point-in-Time Recovery

Write-ahead logs are retained for 7 days, so recovery can target any
second within that window rather than only the nightly snapshot. Recovery
past 7 days can only land on a snapshot boundary.

## Restoring

A restore always creates a new instance; it never overwrites the running
one. The restored instance comes up with a different hostname, and cutting
over is a manual step. This is deliberate — an automatic overwrite turns a
mistaken restore into an unrecoverable one.

## What Is Not Included

Uploaded files are stored outside the database and are not part of the
snapshot. They are versioned separately, with their own 90-day retention.
Restoring the database to an earlier point does not roll files back.
