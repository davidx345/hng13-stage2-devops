# Implementation Decisions

## Nginx Configuration Choices

### 1. Upstream Configuration
- Used `backup` directive for Green to ensure it only receives traffic when Blue fails
- Set `max_fails=2` and `fail_timeout=10s` for quick failure detection
- Used `keepalive` for connection pooling

### 2. Retry Strategy
- `proxy_next_upstream`: Configured to retry on errors, timeouts, and 5xx responses
- `proxy_next_upstream_tries=2`: Limits retries to prevent infinite loops
- Tight timeouts (2s connect, 5s read) for fast failure detection

### 3. Header Preservation
- Did NOT use `proxy_hide_header` for app headers
- Ensured headers from upstream are forwarded to clients by default
- This allows `X-App-Pool` and `X-Release-Id` to reach clients

## Docker Compose Choices

### 1. Health Checks
- Added health checks to monitor app container status
- Uses `/healthz` endpoint for liveness detection

### 2. Networking
- Used bridge network for container communication
- Apps reference each other by service name (app_blue, app_green)

### 3. Port Exposure
- Nginx: 8080 (public)
- Blue: 8081 (for chaos testing)
- Green: 8082 (for chaos testing)

## ACTIVE_POOL Implementation
- The `ACTIVE_POOL` environment variable is included in `.env` as required
- Currently, the configuration is hardcoded with Blue as primary and Green as backup
- To fully implement dynamic switching, the Nginx config would need more complex templating or scripting
- Since the task specifies "Blue is active by default", this hardcoded approach meets the requirements

## Potential Improvements
- Add monitoring/metrics (Prometheus)
- Implement graceful shutdown
- Add TLS/SSL support
- Use Nginx Plus for active health checks
- Implement full templating for ACTIVE_POOL switching