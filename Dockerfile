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

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "app:app"]