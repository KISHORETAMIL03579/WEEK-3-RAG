FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py qdrant_store.py eval_retrieval.py ./
COPY templates/ templates/
COPY static/ static/

RUN mkdir -p uploads vectorstore

EXPOSE 5000

ENV PORT=5000

CMD ["python", "app.py"]

