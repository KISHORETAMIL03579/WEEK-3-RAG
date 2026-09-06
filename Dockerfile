FROM python:3.11-slim-bookworm

WORKDIR /app

# Create non-root system user for production security
RUN useradd --create-home --uid 10001 appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application modules and assets (sample_trace.py singular)
COPY app.py qdrant_store.py eval_retrieval.py trace_store.py sample_trace.py ./
COPY prompts/ prompts/
COPY templates/ templates/
COPY static/ static/

# Pre-create data directories and assign ownership to appuser
RUN mkdir -p uploads vectorstore traces \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 5000

ENV PORT=5000

# FastAPI is ASGI, so Gunicorn can no longer serve `app:app` on its own — it
# runs an ASGI worker class instead. Keeping Gunicorn as the process manager
# preserves the existing worker-count / timeout / graceful-restart operational
# knowledge; the worker class is the only change from the previous WSGI
# command. Route handlers are plain `def`, so each worker runs them in
# uvicorn's threadpool — the same blocking-call concurrency model the Flask +
# Gunicorn sync workers had.
#
# NOTE: uvicorn_worker.UvicornWorker (the `uvicorn-worker` package), not the
# older uvicorn.workers.UvicornWorker — the in-uvicorn module is deprecated
# and emits a DeprecationWarning on import.
CMD ["gunicorn", "app:app", \
     "-k", "uvicorn_worker.UvicornWorker", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "2", \
     "--timeout", "120"]