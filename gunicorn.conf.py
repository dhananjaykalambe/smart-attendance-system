# gunicorn.conf.py
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"
workers = 2
threads = 4
timeout = 120
graceful_timeout = 30
worker_class = 'sync'
loglevel = 'info'
accesslog = '-'
errorlog = '-'