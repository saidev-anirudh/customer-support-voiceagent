# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS base

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

ARG UID=10001
RUN adduser --disabled-password --gecos "" --home "/app" --shell "/sbin/nologin" \
    --no-create-home --uid "${UID}" appuser

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY . .
RUN chown -R appuser:appuser /app
USER appuser

# Pre-download VAD and turn-detector model weights so the first call is fast.
RUN uv run --no-sync main.py download-files

CMD ["uv", "run", "--no-sync", "main.py", "start"]
