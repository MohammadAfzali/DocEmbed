FROM python:3.11-slim
# Install Tesseract and dependencies
#RUN apt-get update && apt-get install -y tesseract-ocr libtesseract-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY celery_app.py .
RUN pip install --no-cache-dir celery qdrant-client boto3 #unstructured[pdf]
CMD ["celery", "-A", "celery_app", "worker", "--loglevel=info", "--queues=celery"]