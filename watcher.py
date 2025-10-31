#!/usr/bin/env python3
import os
import time
import re
import requests
from collections import deque
from datetime import datetime, timedelta

# Configuration from environment
SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL', '')
ERROR_RATE_THRESHOLD = float(os.getenv('ERROR_RATE_THRESHOLD', 2))
WINDOW_SIZE = int(os.getenv('WINDOW_SIZE', 200))
ALERT_COOLDOWN_SEC = int(os.getenv('ALERT_COOLDOWN_SEC', 300))
LOG_FILE = '/var/log/nginx/access_real.log'

# State tracking
last_pool = None
request_window = deque(maxlen=WINDOW_SIZE)
last_failover_alert_time = {}
last_error_rate_alert_time = datetime.min


def send_slack_alert(title, message, alert_type='info'):
    """Send an alert to Slack."""
    if not SLACK_WEBHOOK_URL:
        print(f"[ALERT] {title}: {message}")
        return
    
    color_map = {
        'failover': '#FF6B6B',
        'error': '#FFA500',
        'info': '#4A90E2'
    }
    
    payload = {
        'attachments': [
            {
                'fallback': f"{title}: {message}",
                'title': title,
                'text': message,
                'color': color_map.get(alert_type, color_map['info']),
                'footer': 'Blue/Green Watcher',
                'ts': int(time.time())
            }
        ]
    }
    
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=5)
        if response.status_code == 200:
            print(f"[SENT] {title}")
        else:
            print(f"[FAILED] Slack alert failed: {response.status_code}")
    except Exception as e:
        print(f"[ERROR] Failed to send Slack alert: {e}")


def parse_log_line(line):
    """Parse Nginx log line to extract pool, release, upstream_status, upstream."""
    try:
        # Pattern: pool=<pool> release=<release> upstream_status=<status> upstream=<addr>
        pool_match = re.search(r'pool=(\S+)', line)
        release_match = re.search(r'release=(\S+)', line)
        status_match = re.search(r'upstream_status=(\S+)', line)
        upstream_match = re.search(r'upstream=(\S+)', line)
        request_time_match = re.search(r'request_time=([\d.]+)', line)
        
        if status_match:
            pool_value = pool_match.group(1) if pool_match else '-'
            upstream_addr = upstream_match.group(1) if upstream_match else '-'
            
            # If pool is -, try to infer from upstream address
            # Assuming app_blue typically gets .3 and app_green gets .2 (Docker assigns sequentially)
            # This is a fallback - adjust based on your actual upstream IPs
            if pool_value == '-' and upstream_addr != '-':
                # Extract last octet or use port to identify
                # Check multiple upstream (comma-separated for retries)
                upstreams = upstream_addr.split(',')
                # Use the last successful upstream (rightmost)
                final_upstream = upstreams[-1].strip()
                
                # Map IP to pool (heuristic: check if it's blue or green container)
                if ':8080' in final_upstream:
                    # You can adjust this logic based on actual container IPs
                    # For now, we'll keep original pool value
                    pool_value = pool_value
            
            return {
                'pool': pool_value,
                'release': release_match.group(1) if release_match else '-',
                'upstream_status': status_match.group(1),
                'upstream': upstream_addr,
                'request_time': float(request_time_match.group(1)) if request_time_match else 0,
                'timestamp': datetime.now()
            }
    except Exception as e:
        print(f"[PARSE_ERROR] {e}")
    
    return None


def detect_failover(current_pool, current_upstream):
    """Detect if a failover event occurred based on pool or upstream address."""
    global last_pool
    
    # Determine effective pool from upstream if pool is '-'
    effective_pool = current_pool
    if current_pool == '-' and current_upstream != '-':
        # Extract the final upstream that served the request
        upstreams = current_upstream.split(',')
        final_upstream = upstreams[-1].strip()
        
        # Map upstream IP to pool name (heuristic based on typical Docker networking)
        # app_blue is typically .3, app_green is typically .2
        if '.3:8080' in final_upstream or 'app_blue' in final_upstream:
            effective_pool = 'blue'
        elif '.2:8080' in final_upstream or 'app_green' in final_upstream:
            effective_pool = 'green'
        else:
            # Use the full upstream address as identifier
            effective_pool = final_upstream
    
    if last_pool is None:
        last_pool = effective_pool
        return False, effective_pool
    
    if effective_pool != last_pool and effective_pool != '-':
        return True, effective_pool
    
    return False, effective_pool


def check_error_rate():
    """Check if error rate exceeds threshold."""
    if len(request_window) == 0:
        return False
    
    error_count = sum(1 for req in request_window if req['upstream_status'] in ['500', '502', '503', '504', '-'])
    error_rate = (error_count / len(request_window)) * 100
    
    return error_rate > ERROR_RATE_THRESHOLD, error_rate, error_count


def should_send_alert(alert_type, cooldown_key):
    """Check if enough time has passed since last alert (cooldown)."""
    now = datetime.now()
    last_time = last_failover_alert_time.get(cooldown_key, datetime.min)
    
    if (now - last_time).total_seconds() >= ALERT_COOLDOWN_SEC:
        last_failover_alert_time[cooldown_key] = now
        return True
    
    return False


def tail_log_file():
    """Tail the Nginx log file and process new lines."""
    global last_pool, last_error_rate_alert_time
    
    print(f"[START] Watching {LOG_FILE}")
    print(f"[CONFIG] Threshold: {ERROR_RATE_THRESHOLD}%, Window: {WINDOW_SIZE}, Cooldown: {ALERT_COOLDOWN_SEC}s")
    
    if not os.path.exists(LOG_FILE):
        print(f"[WAIT] Log file not found, waiting for {LOG_FILE}...")
        while not os.path.exists(LOG_FILE):
            time.sleep(1)
    
    # Start tailing from end of file
    with open(LOG_FILE, 'r') as f:
        f.seek(0, 2)  # Go to end
        
        while True:
            line = f.readline()
            
            if not line:
                time.sleep(0.5)
                continue
            
            line = line.strip()
            if not line:
                continue
            
            # Parse log line
            parsed = parse_log_line(line)
            if not parsed:
                continue
            
            # Add to window
            request_window.append(parsed)
            
            current_pool = parsed['pool']
            current_upstream = parsed['upstream']
            print(f"[LOG] pool={current_pool} status={parsed['upstream_status']} upstream={current_upstream}")
            
            # Check for failover
            failover_detected, effective_pool = detect_failover(current_pool, current_upstream)
            if failover_detected:
                if should_send_alert('failover', f"failover_{last_pool}_{effective_pool}"):
                    send_slack_alert(
                        ':warning: Failover Detected',
                        f"Primary pool switched from `{last_pool}` to `{effective_pool}`\nRelease: `{parsed['release']}`\nUpstream: `{current_upstream}`",
                        'failover'
                    )
                last_pool = effective_pool
            
            # Check error rate
            exceeds, rate, count = check_error_rate()
            if exceeds and should_send_alert('error_rate', 'error_rate'):
                send_slack_alert(
                    ':chart_with_upwards_trend: High Error Rate',
                    f"Error rate: {rate:.1f}% ({count}/{len(request_window)} requests) - Threshold: {ERROR_RATE_THRESHOLD}%",
                    'error'
                )


if __name__ == '__main__':
    try:
        tail_log_file()
    except KeyboardInterrupt:
        print("\n[STOP] Watcher stopped")
    except Exception as e:
        print(f"[FATAL] {e}")
        send_slack_alert(':x: Watcher Error', f"Log watcher crashed: {e}", 'error')
