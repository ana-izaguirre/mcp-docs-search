# Security

## Encryption in Transit

All traffic must use TLS. Terminate TLS at the load balancer; the service
itself runs plain HTTP on the internal network. Use a minimum of TLS 1.2.
Certificates are managed by the platform, not by the service.

## Credentials

Never commit credentials to version control. Load them from a secret
manager at runtime. The service reads `CLIENT_ID` and `CLIENT_SECRET` from
the environment at startup. Rotate credentials by updating the secret and
restarting; there is no hot rotation.

## Token Storage

The service caches validated tokens in memory for five minutes to avoid
re-validating on every request. Tokens are never written to disk. On
restart the cache is empty and repopulates on demand.

## Audit

Security-relevant events — authentication failures, permission denials,
credential rotations — are logged at warn level with the actor and target.
Forward these logs to your security information system.
