# Data Model

## Entities

The service manages three core entities: accounts, projects, and members.
An account owns many projects. A project belongs to exactly one account.
A member is a user's membership in a project, with a role. Deleting an
account cascades to its projects and their members.

## Schemas

Each entity has a schema defining its fields, types, and constraints. Schemas
are versioned. When a schema changes, a migration applies the change to
existing data. The current schema version is recorded in the `schema_migrations`
table and incremented on every change.

## Relationships

A project references its account by ID. A member references both a project
and a user. These references are enforced at the application level, not by
foreign keys in the database. Queries that span entities are assembled in
the application layer.

## Versioning

Schema versions are monotonically increasing integers. A migration can only
be applied if the current version is exactly one less than the target. This
prevents a migration from being skipped or applied out of order.
