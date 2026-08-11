# Authentication

## Overview

Every request must carry a bearer token in the `Authorization` header.
Requests without a valid token receive a 401 response. Tokens are issued
by your identity provider and validated locally using a public key.

## OAuth 2.0

The service acts as a resource server in an OAuth 2.0 flow. It does not
issue tokens itself — it only validates them. Obtain tokens from your
identity provider's token endpoint using the client credentials grant
for service-to-service calls, or the authorization code grant for user
delegation.

## Token Validation

On each request the service checks the token signature against a cached
public key, verifies the expiry, and confirms the audience claim matches
this service. A token that fails any of these checks is rejected with
401. There is no refresh mechanism; the client must obtain a new token
when the current one expires.

## Credentials

Store client credentials in a secret manager, never in source code. The
service reads them at startup from the `CLIENT_ID` and `CLIENT_SECRET`
environment variables. Rotate credentials by updating the secret and
restarting the service.
