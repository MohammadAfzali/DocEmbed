import os
import uuid

import boto3
from celery import Celery
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue, VectorParams, Distance
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Celery with RabbitMQ
app = Celery(
    'celery_app',
    broker='amqp://guest:guest@rabbitmq.qdrant.svc.cluster.local:5672//',
    backend='rpc://'
)

# Configure Celery
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

# Initialize AWS S3 client
try:
    s3_client = boto3.client('s3', region_name='us-east-2')
    logger.info("Successfully initialized S3 client")
except Exception as e:
    logger.error(f"Failed to initialize S3 client: {e}")
    raise

# Initialize Qdrant client
try:
    qdrant_client = QdrantClient(url='http://qdrant.qdrant.svc.cluster.local:6333', timeout=10)
    logger.info("Successfully connected to Qdrant")
except Exception as e:
    logger.error(f"Failed to connect to Qdrant: {e}")
    raise

"""Ensure Qdrant collection exists with correct configuration"""
try:
    collections = qdrant_client.get_collections()
    if 'test_collection' not in [c.name for c in collections.collections]:
        qdrant_client.create_collection(
            collection_name='test_collection',
            vectors_config=VectorParams(size=384, distance=Distance.COSINE)
        )
        logger.info("Created test_collection with vector size 384")
    else:
        logger.info("test_collection already exists")
except Exception as e:
    logger.error(f"Failed to ensure Qdrant collection: {e}")
    raise


def parse_text(file_content):
    """Parse text content into paragraph chunks"""
    try:
        # Decode bytes to string
        text = file_content.decode('utf-8')
        # Split into paragraphs (using double newline as separator)
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        return paragraphs
    except Exception as e:
        logger.error(f"Failed to parse text: {e}")
        raise


@app.task(name='celery_app.process_s3_text')
def process_s3_text(bucket_name='my-unique-bucket-2025123243'):
    """Celery task to process text files in S3 bucket"""
    logger.info(f"Starting task process_s3_text for bucket {bucket_name}")
    try:
        # List text files in S3 bucket
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix='', Delimiter='/')
        text_files = [
            obj['Key'] for obj in response.get('Contents', [])
            if obj['Key'].endswith('.txt')
        ]
        logger.info(f"Found {len(text_files)} text files in bucket {bucket_name}")

        for text_key in text_files:
            # Extract doc_id from filename (e.g., 'test_file' from 'test_file.txt')
            doc_id = os.path.splitext(text_key)[0]
            logger.info(f"Checking {text_key} with doc_id {doc_id}")

            # Check if doc_id exists in Qdrant (any chunk with this doc_id)
            search_result = qdrant_client.scroll(
                collection_name='test_collection',
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key='doc_id',
                            match=MatchValue(value=doc_id)
                        )
                    ]
                ),
                limit=1
            )

            if search_result[0]:  # doc_id exists in Qdrant
                logger.info(f"Skipping {text_key}: doc_id {doc_id} already in Qdrant")
                continue

            # Download and parse text file
            logger.info(f"Processing {text_key}")
            obj = s3_client.get_object(Bucket=bucket_name, Key=text_key)
            text_content = obj['Body'].read()
            paragraphs = parse_text(text_content)

            # Process each paragraph chunk
            for index, text in enumerate(paragraphs):
                chunk_id = str(uuid.uuid4())
                logger.info(f"Sending chunk {chunk_id} for {text_key}, text length: {len(text)}")
                # Publish chunk to RabbitMQ queue
                app.send_task(
                    'embed_app.store_chunk_content',
                    args=(doc_id, chunk_id, text),
                    queue='chunk_content_queue'
                )
                logger.info(f"Sent chunk {chunk_id} for {text_key} to chunk_content_queue")

    except Exception as e:
        logger.error(f"Error processing text files: {e}")
        raise


def trigger_process():
    """Trigger the text file processing task"""
    try:
        result = app.send_task('celery_app.process_s3_text')
        logger.info(f"Triggered text file processing task: {result.id}")
        return result
    except Exception as e:
        logger.error(f"Failed to trigger task: {e}")
        raise


if __name__ == '__main__':
    trigger_process()
