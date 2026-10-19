# UNTESTED: Docker is not available in the authoring environment.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATABASE_URL=sqlite:////data/salary.db

WORKDIR /app

# Dependencies first for better layer caching.
COPY pyproject.toml ./
COPY app ./app
RUN pip install .

COPY alembic.ini docker-entrypoint.sh ./
COPY alembic ./alembic
COPY scripts ./scripts
# Tolerate CRLF checkouts on Windows.
RUN sed -i 's/\r$//' docker-entrypoint.sh

RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /data /app
USER appuser

EXPOSE 8000
ENTRYPOINT ["sh", "/app/docker-entrypoint.sh"]
