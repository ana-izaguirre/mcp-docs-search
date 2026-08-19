# Permissions

## Roles

Three roles exist: viewer, editor and owner. A viewer can read every
resource in the workspace. An editor can additionally create and modify
resources but cannot delete them. An owner can do everything, including
managing members and deleting the workspace.

## Scopes on Keys

An API key carries a subset of its creator's permissions, never more. A key
created by an editor cannot be granted delete access, even by an owner —
raising it requires a new key from an account that holds the permission.

## Checking Access

Permission checks happen before validation, so a request that is both
malformed and unauthorised is answered with a permission error rather than
a validation error. This avoids telling an unauthorised caller whether a
resource exists.

## Inheritance

Permissions are set at the workspace level and apply to every resource
inside it. There is no per-resource override. Finer-grained access is
expressed by splitting resources into separate workspaces.
