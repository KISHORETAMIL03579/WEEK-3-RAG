FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py qdrant_store.py eval_retrieval.py trace_store.py sample_traces.py ./
COPY templates/ templates/
COPY static/ static/

RUN mkdir -p uploads vectorstore traces

EXPOSE 5000

ENV PORT=5000

CMD ["python", "app.py"]