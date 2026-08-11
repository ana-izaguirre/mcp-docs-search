# Deployment

## Overview

The service ships as a single container image. It is stateless: no data
is written to local disk, so any instance can be destroyed and replaced
without loss. Configuration is passed entirely through environment
variables — there are no config files to mount.

## Container

Build and run with Docker:

```bash
docker build -t myapp/service .
docker run -p 8080:8080 \
  -e PORT=8080 \
  -e LOG_LEVEL=info \
  myapp/service
```

The image exposes port 8080. Map it to any host port with the `-p` flag.
The container listens on all interfaces inside the network, so binding
to `0.0.0.0` is the default and should not be changed.

## Environment

All configuration is supplied via environment variables. The service
reads them once at startup; changing a variable requires a restart. There
is no hot-reload. The full list of variables is documented in the
configuration guide.

## Health Check

A `/health` endpoint returns 200 when the service is ready to accept
traffic. Use it as a liveness probe in orchestrators. The endpoint does
not check downstream dependencies — it only confirms the process is
running and the port is bound.

## Scaling

Scale horizontally.
