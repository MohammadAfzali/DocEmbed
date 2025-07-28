FROM python:3.11-slim
WORKDIR /app
COPY embed_app.py .
RUN pip install --no-cache-dir celery qdrant-client==1.9.0 fastembed
CMD ["celery", "-A", "embed_app", "worker", "--loglevel=info", "--queues=chunk_content_queue"]
