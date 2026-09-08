# Telegram bot image (`todo telegram serve`). Built and run locally on the
# k3s node — see k3s/telegram-bot/README.md — not published to a registry.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN useradd --create-home --shell /bin/bash appuser

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

COPY pyproject.toml uv.lock README.md ./
COPY src/ src/
RUN uv sync --frozen --no-dev

RUN mkdir -p /home/appuser/.local/share/todo /home/appuser/.config/todo && \
    chown -R appuser:appuser /app /home/appuser

USER appuser

ENV PATH="/app/.venv/bin:${PATH}"

ENTRYPOINT ["todo", "telegram", "serve"]
