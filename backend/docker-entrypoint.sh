#!/bin/sh
# Start the API: bring the database schema up to date, then serve on $PORT.
set -e

if [ "${FPLAI_RUN_MIGRATIONS:-1}" = "1" ]; then
  alembic upgrade head
fi

# --proxy-headers: Cloud Run sits behind Google's proxy, so the visitor's address comes
# from X-Forwarded-For (the rate limit keys on it).
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}" --proxy-headers --forwarded-allow-ips="*"
