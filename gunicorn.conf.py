"""
FraudGuard AI - Production Gunicorn WSGI Configuration
Tuned for containerized and cloud deployments (Render, Docker, AWS, GCP).
"""

import os
import multiprocessing

# 1. Server Socket Binding
# Binds to 0.0.0.0 and dynamically respects $PORT assigned by cloud providers (Render, Heroku, Cloud Run)
port = os.environ.get("PORT", "5000")
bind = f"0.0.0.0:{port}"

# 2. Worker Processes & Concurrency
# In production free-tier containers (e.g. Render 512MB RAM), default to 2 workers and 2 threads
default_workers = int(os.environ.get("WEB_CONCURRENCY", 2))
workers = default_workers
threads = int(os.environ.get("GUNICORN_THREADS", 2))
worker_class = "gthread"

# 3. Worker Lifecycle & Memory Leak Mitigation
# Automatically cycle worker processes after handling requests to prevent scikit-learn/pandas memory bloat
max_requests = int(os.environ.get("GUNICORN_MAX_REQUESTS", 1000))
max_requests_jitter = int(os.environ.get("GUNICORN_MAX_REQUESTS_JITTER", 100))

# 4. Connection Timeouts & Keep-Alive
# 120s timeout handles multi-row batch ML predictions comfortably; 5s keepalive optimizes connection reuse
timeout = int(os.environ.get("GUNICORN_TIMEOUT", 120))
keepalive = int(os.environ.get("GUNICORN_KEEPALIVE", 5))

# 5. Logging Configuration
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)sµs'

# 6. Process Identification
proc_name = "fraudguard_ai_wsgi"
