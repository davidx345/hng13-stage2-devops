# DevOps Stage 2 & 3 - Blue/Green Deployment with Observability

## Overview
This project implements a Blue/Green deployment pattern with automatic failover using Nginx as a reverse proxy, plus real-time monitoring and Slack alerting for operational visibility.

## Architecture
- **Nginx**: Reverse proxy with health-based failover and custom access logging
- **Blue App**: Primary application instance (port 8081)
- **Green App**: Backup application instance (port 8082)
- **Alert Watcher**: Python service that monitors logs and sends Slack alerts
- **Public Endpoint**: http://localhost:8080

## Prerequisites
- Docker
- Docker Compose
- Slack workspace with incoming webhook configured

## Setup

1. Clone this repository

2. Create a Slack incoming webhook:
   - Go to https://api.slack.com/apps
   - Create a new app or select existing
   - Enable "Incoming Webhooks"
   - Add webhook to your channel
   - Copy the webhook URL

3. Copy `.env.example` to `.env` and update configuration:
```bash
   cp .env.example .env
```

4. Update the values in `.env`:
```env
   BLUE_IMAGE=<your-blue-image-url>
   GREEN_IMAGE=<your-green-image-url>
   SLACK_WEBHOOK_URL=<your-slack-webhook-url>
   ERROR_RATE_THRESHOLD=2
   WINDOW_SIZE=200
   ALERT_COOLDOWN_SEC=300
```

## Running

Start all services:
```bash
docker-compose up -d
```

Check logs:
```bash
docker-compose logs -f
```

Stop services:
```bash
docker-compose down
```

## Testing Failover and Alerts

### 1. Test Normal Operation
```bash
curl http://localhost:8080/version
```
Expected: Returns 200, served by Blue pool

### 2. Trigger Failover and Alert
```bash
# Induce chaos on Blue
curl -X POST http://localhost:8081/chaos/start?mode=error

# Make requests to trigger failover
for i in {1..5}; do curl http://localhost:8080/version; sleep 1; done
```
Expected: 
- Traffic switches to Green automatically
- Slack alert: "⚠️ Failover Detected"

### 3. Trigger High Error Rate Alert
```bash
# Keep chaos running and make many requests
for i in {1..50}; do curl -s http://localhost:8080/version > /dev/null; sleep 0.1; done
```
Expected:
- Slack alert: "📈 High Error Rate" (if >2% errors in last 200 requests)

### 4. Stop Chaos and Verify Recovery
```bash
curl -X POST http://localhost:8081/chaos/stop
curl http://localhost:8080/version
```

## Viewing Logs

### Nginx Access Logs
```bash
docker logs nginx_proxy
```

### Watcher Logs
```bash
docker logs -f alert_watcher
```

### Container Shell (for log file inspection)
```bash
docker exec -it nginx_proxy sh
ls -la /var/log/nginx/
```

## Configuration

All configuration is managed through `.env`:
- `BLUE_IMAGE`: Docker image for Blue instance
- `GREEN_IMAGE`: Docker image for Green instance
- `ACTIVE_POOL`: Active pool (blue|green) - Note: Currently hardcoded to blue as primary
- `RELEASE_ID_BLUE`: Release identifier for Blue
- `RELEASE_ID_GREEN`: Release identifier for Green
- `PORT`: Application internal port (default: 8080)

## Failover Behavior

- **Primary**: Blue (max_fails=2, fail_timeout=10s)
- **Backup**: Green (only receives traffic when Blue fails)
- **Retry Logic**: Automatic retry on errors (500, 502, 503, 504, timeout)
- **Timeouts**:
  - Connect: 2s
  - Send: 5s
  - Read: 5s

## Header Forwarding

The following headers are preserved and forwarded to clients:
- `X-App-Pool`: Identifies which pool served the request (blue|green)
- `X-Release-Id`: Release identifier of the serving instance

## Observability Features (Stage 3)

### Custom Nginx Logging
- Logs capture: pool, release, upstream_status, upstream address, request_time, upstream_response_time
- Logs stored in shared volume accessible to watcher service

### Alert Watcher
- Real-time log monitoring using Python
- Detects failover events (pool changes)
- Tracks error rate over rolling window
- Sends alerts to Slack with cooldown/deduplication
- Configurable thresholds via environment variables

### Slack Alerts
- **Failover Alert**: Triggered when traffic switches between pools
- **High Error Rate Alert**: Triggered when 5xx rate exceeds threshold
- **Watcher Error Alert**: Triggered if monitoring service crashes

### Runbook
See [runbook.md](runbook.md) for detailed alert meanings and operator response procedures.

## Screenshots

For Stage 3 submission, the following screenshots are included:
1. Slack alert showing failover detection
2. Slack alert showing high error rate
3. Nginx log snippet with structured fields

## Troubleshooting

### No Slack alerts appearing
- Verify `SLACK_WEBHOOK_URL` is set correctly in `.env`
- Check watcher logs: `docker logs alert_watcher`
- Test webhook manually using curl

### Logs not showing pool/release values
- Open-source Nginx cannot log upstream response headers directly
- Failover detection works via upstream IP address mapping as fallback
- See DECISION.md for technical explanation

### Watcher not detecting failover
- Ensure chaos mode is active: `curl -X POST http://localhost:8081/chaos/start?mode=error`
- Make multiple requests to trigger pool switch
- Check watcher logs for parsing errors