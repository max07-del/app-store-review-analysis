FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_DATABASE_PATH=/data/app_store_reviews.db

WORKDIR /srv

COPY pyproject.toml README.md ./
COPY app ./app

RUN pip install --no-cache-dir . \
    && mkdir -p /data \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser /data /srv

COPY scripts ./scripts

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

# Render, Fly, Heroku and Cloud Run all inject the listening port through $PORT.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
