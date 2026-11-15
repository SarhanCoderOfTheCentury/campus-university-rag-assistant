#!/bin/sh
cd /var/task
exec python -m uvicorn backend.aws_app:app --host 0.0.0.0 --port 8000 --no-access-log
