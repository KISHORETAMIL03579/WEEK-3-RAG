# Stage 1: Build React 18 + TypeScript + Vite frontend
FROM node:22-alpine AS frontend-builder
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Production Python / FastAPI runtime
FROM python:3.11-slim-bookworm

WORKDIR /app

# Create non-root system user for production security
RUN useradd --create-home --uid 10001 appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application modules and assets
COPY app.py qdrant_store.py eval_retrieval.py trace_store.py sample_trace.py ./
COPY prompts/ prompts/

# Copy compiled React frontend assets from builder stage
COPY --from=frontend-builder /build/frontend/dist ./frontend/dist

# Pre-create data directories and assign ownership to appuser
RUN mkdir -p uploads vectorstore traces \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 5000

ENV PORT=5000

# FastAPI is ASGI: Gunicorn runs with uvicorn_worker.UvicornWorker ASGI worker
CMD ["gunicorn", "app:app", \
     "-k", "uvicorn_worker.UvicornWorker", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "2", \
     "--timeout", "120"]