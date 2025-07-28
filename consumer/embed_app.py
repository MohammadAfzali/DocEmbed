from celery import Celery
from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct, VectorParams, Distance
from qdrant_client.http.exceptions import UnexpectedResponse
from fastembed import TextEmbedding
import logging
import numpy as np

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Celery with RabbitMQ
app = Celery(
    'embed_app',
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

# Initialize FastEmbed model
try:
    embedding_model = TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")
    logger.info("Successfully initialized FastEmbed model")
except Exception as e:
    logger.error(f"Failed to initialize FastEmbed model: {e}")
    raise

@app.task(name='embed_app.store_chunk_content')
def store_pdf_content(doc_id, chunk_id, text):
    """Task to generate embeddings and store in Qdrant"""
    logger.info(f"Task embed_app.store_chunk_content received for doc_id {doc_id}, chunk_id {chunk_id}, text length: {len(text)}")
    try:
        # Validate inputs
        if not isinstance(doc_id, str):
            logger.error(f"Invalid doc_id type: {type(doc_id)}, value: {doc_id}")
            raise ValueError(f"doc_id must be a string, got {type(doc_id)}")
        if not isinstance(chunk_id, str):
            logger.error(f"Invalid chunk_id type: {type(chunk_id)}, value: {chunk_id}")
            raise ValueError(f"chunk_id must be a string, got {type(chunk_id)}")

        # Generate embedding for the text
        logger.info(f"Generating embedding for chunk_id {chunk_id}")
        embeddings = list(embedding_model.embed([text]))[0]
        embedding_vector = embeddings.tolist()  # Convert to list for Qdrant
        logger.info(f"Generated embedding for chunk_id {chunk_id}, vector length: {len(embedding_vector)}")

        # Validate embedding vector
        if len(embedding_vector) != 384:
            logger.error(f"Invalid embedding vector length: {len(embedding_vector)}, expected 384")
            raise ValueError(f"Embedding vector length {len(embedding_vector)} does not match expected 384")

        # Upsert into Qdrant
        logger.info(f"Upserting embedding for chunk_id {chunk_id} into Qdrant")
        qdrant_client.upsert(
            collection_name='test_collection',
            points=[
                PointStruct(
                    id=chunk_id,  # Use chunk_id as the unique point ID
                    vector=embedding_vector,
                    payload={"doc_id": doc_id, "text": text}
                )
            ]
        )
        logger.info(f"Successfully upserted embedding for chunk_id {chunk_id} into Qdrant")

    except UnexpectedResponse as e:
        logger.error(f"Qdrant API error for chunk_id {chunk_id}: status={e.status_code}, details={str(e)}")
        raise
    except Exception as e:
        logger.error(f"Failed to store content for chunk_id {chunk_id}: {e}")
        raise