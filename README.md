# DevOps Stage 2 - Blue/Green Deployment with Nginx

## Overview
This project implements a Blue/Green deployment pattern with automatic failover using Nginx as a reverse proxy.

## Architecture
- **Nginx**: Reverse proxy with health-based failover
- **Blue App**: Primary application instance (port 8081)
- **Green App**: Backup application instance (port 8082)
- **Public Endpoint**: http://localhost:8080

## Prerequisites
- Docker
- Docker Compose

## Setup

1. Clone this repository
2. Copy `.env.example` to `.env` and update image URLs:
```bash
   cp .env.example .env
```

3. Update the image URLs in `.env`:
```env
   BLUE_IMAGE=<your-blue-image-url>
   GREEN_IMAGE=<your-green-image-url>
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

## Testing Failover

1. **Normal operation** (should route to Blue):
```bash
   curl http://localhost:8080/version
```

2. **Trigger chaos on Blue**:
```bash
   curl -X POST http://localhost:8081/chaos/start?mode=error
```

3. **Verify automatic failover** (should now route to Green):
```bash
   curl http://localhost:8080/version
```

4. **Stop chaos**:
```bash
   curl -X POST http://localhost:8081/chaos/stop
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