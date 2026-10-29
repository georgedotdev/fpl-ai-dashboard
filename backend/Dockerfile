# The API as a container, for Google Cloud Run (or any host that runs containers).
# Build from the backend/ folder:  docker build -t fpl-ai-api backend
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first, so code changes don't reinstall them.
COPY pyproject.toml ./
RUN mkdir app && touch app/__init__.py && pip install . && rm -rf app

COPY app ./app
RUN pip install --no-deps .
COPY alembic.ini docker-entrypoint.sh ./
COPY migrations ./migrations

# Cloud Run sends traffic to $PORT (8080 by default).
EXPOSE 8080
CMD ["sh", "docker-entrypoint.sh"]
