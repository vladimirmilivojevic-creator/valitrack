#!/bin/sh
# Start script of the container: create or update the database, load the demo data once, run the server.
set -e

alembic upgrade head

if [ "$DEMO_MODE" = "true" ]; then
    python -m app.seed.demo
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="*"
