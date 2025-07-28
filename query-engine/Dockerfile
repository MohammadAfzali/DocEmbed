FROM python:3.11-slim
WORKDIR /app
COPY query_service.py .
RUN pip install --no-cache-dir flask qdrant-client==1.9.0 fastembed
CMD ["python", "query_service.py"]