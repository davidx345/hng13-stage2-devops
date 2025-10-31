# Blue/Green Deployment Runbook

## Overview
This runbook describes how to respond to alerts from the Blue/Green deployment monitoring system.

## Alert Types

### 1. ⚠️ Failover Detected

**What it means:**  
The primary application pool has failed and traffic has automatically switched to the backup pool.

**Example alert:**
```
⚠️ Failover Detected
Primary pool switched from blue to green
Release: v1.1.0-green
```

**Operator Actions:**
1. **Acknowledge the alert** - Failover is automatic and traffic is now being served by the backup pool.
2. **Check the health of the failed pool:**
   ```bash
   docker logs app_blue
   docker exec app_blue wget -qO- http://localhost:8080/healthz
   ```
3. **Investigate the cause:**
   - Check application logs for errors
   - Review recent deployments or changes
   - Check resource utilization (CPU, memory)
4. **Stop chaos mode if active:**
   ```bash
   curl -X POST http://localhost:8081/chaos/stop
   ```
5. **Monitor the backup pool** to ensure it's handling traffic correctly.
6. **Plan recovery:**
   - Fix the issue in the failed pool
   - Test thoroughly before switching back
   - Consider scheduled maintenance window for pool switch

**Recovery Steps:**
1. Fix the root cause in the failed pool
2. Restart the container if needed:
   ```bash
   docker-compose restart app_blue
   ```
3. Verify health:
   ```bash
   curl http://localhost:8081/healthz
   ```
4. Monitor logs to confirm stability

---

### 2. 📈 High Error Rate

**What it means:**  
The upstream application is returning 5xx errors at a rate exceeding the configured threshold (default: 2% over last 200 requests).

**Example alert:**
```
📈 High Error Rate
Error rate: 5.2% (10/200 requests) - Threshold: 2%
Current 5xx rate: 100.00%
```

**Operator Actions:**
1. **Check which pool is currently active:**
   ```bash
   docker logs nginx_proxy | tail -20
   ```
2. **Inspect upstream application logs:**
   ```bash
   docker logs app_blue
   docker logs app_green
   ```
3. **Check application health endpoints:**
   ```bash
   curl http://localhost:8081/healthz  # Blue
   curl http://localhost:8082/healthz  # Green
   ```
4. **Verify resource availability:**
   ```bash
   docker stats
   ```
5. **Stop chaos mode if active:**
   ```bash
   curl -X POST http://localhost:8081/chaos/stop
   curl -X POST http://localhost:8082/chaos/stop
   ```
6. **Consider manual pool toggle if one pool is consistently failing:**
   - Modify ACTIVE_POOL in .env
   - Restart services:
     ```bash
     docker-compose restart
     ```

**Investigation Steps:**
- Check for recent code deployments
- Review database connectivity
- Check external service dependencies
- Review application metrics and logs
- Check for resource exhaustion (memory leaks, CPU spikes)

---

### 3. ❌ Watcher Error

**What it means:**  
The log-watcher process itself has crashed or encountered a fatal error.

**Example alert:**
```
❌ Watcher Error
Log watcher crashed: [error details]
```

**Operator Actions:**
1. **Check watcher container status:**
   ```bash
   docker ps -a | grep alert_watcher
   ```
2. **Check watcher logs:**
   ```bash
   docker logs alert_watcher
   ```
3. **Restart the watcher:**
   ```bash
   docker-compose restart alert_watcher
   ```
4. **Verify log volume is accessible:**
   ```bash
   docker exec alert_watcher ls -la /var/log/nginx/
   ```
5. **Check configuration:**
   - Verify SLACK_WEBHOOK_URL is set correctly in .env
   - Verify all environment variables are valid

---

## Maintenance Mode

### Suppressing Alerts During Planned Maintenance

To prevent alert spam during planned maintenance or pool toggles:

**Option 1: Temporarily stop the watcher**
```bash
docker-compose stop alert_watcher
# Perform maintenance
docker-compose start alert_watcher
```

**Option 2: Set a high alert cooldown**
```bash
# Edit .env
ALERT_COOLDOWN_SEC=3600  # 1 hour

# Restart watcher
docker-compose restart alert_watcher
```

**Option 3: Remove Slack webhook temporarily**
```bash
# Edit .env and comment out webhook
# SLACK_WEBHOOK_URL=https://...

# Restart watcher
docker-compose restart alert_watcher
```

---

## Common Scenarios

### Scenario 1: Planned Deployment
1. Stop the watcher or increase cooldown
2. Deploy to the inactive pool (e.g., Green if Blue is active)
3. Test the new deployment
4. Trigger pool switch (via configuration or manual failover)
5. Re-enable alerting
6. Monitor for issues

### Scenario 2: Unexpected Failover During Low Traffic
1. Acknowledge the alert
2. Check if it's a transient issue (single request failure)
3. Monitor for pattern of errors
4. Investigate during business hours if no ongoing issues

### Scenario 3: Cascading Failures
1. If both pools are showing errors, check external dependencies
2. Check database connectivity
3. Review infrastructure-level issues (network, DNS, load balancer)
4. Consider emergency rollback if recent deployment

---

## Monitoring Commands

### View Live Nginx Logs
```bash
docker logs -f nginx_proxy
```

### View Watcher Output
```bash
docker logs -f alert_watcher
```

### Check All Container Health
```bash
docker-compose ps
docker-compose logs --tail=50
```

### Manual Failover Test
```bash
# Trigger chaos on Blue
curl -X POST http://localhost:8081/chaos/start?mode=error

# Verify Green takes over
for i in {1..10}; do curl http://localhost:8080/version; sleep 1; done

# Stop chaos
curl -X POST http://localhost:8081/chaos/stop
```

---

## Configuration Reference

### Environment Variables (.env)
- `SLACK_WEBHOOK_URL` - Slack webhook for alerts
- `ERROR_RATE_THRESHOLD` - Error rate % threshold (default: 2)
- `WINDOW_SIZE` - Rolling window size for error rate (default: 200)
- `ALERT_COOLDOWN_SEC` - Seconds between duplicate alerts (default: 300)

### Adjusting Sensitivity
- **More sensitive:** Decrease ERROR_RATE_THRESHOLD or WINDOW_SIZE
- **Less sensitive:** Increase ERROR_RATE_THRESHOLD or WINDOW_SIZE
- **Reduce alert spam:** Increase ALERT_COOLDOWN_SEC

---

## Escalation

If you cannot resolve the issue:
1. Page the on-call engineer
2. Check the incident response playbook
3. Consider rolling back to last known good state
4. Notify stakeholders of ongoing issues

---

## Additional Resources
- Application documentation: [link]
- Infrastructure diagrams: [link]
- Incident response procedures: [link]
- Contact information: [link]
