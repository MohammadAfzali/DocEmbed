from flask import Flask, request, jsonify
from qdrant_client import QdrantClient
from fastembed import TextEmbedding
import logging
import numpy as np

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Initialize Qdrant client
try:
    qdrant_client = QdrantClient(url='http://qdrant.qdrant.svc.cluster.local:6333', timeout=10)
    logger.info("Successfully connected to Qdrant")
except Exception as e:
    logger.error(f"Failed to connect to Qdrant: {e}")
    raise

# Initialize FastEmbed model
try:
    embedding_model = TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")
    logger.info("Successfully initialized FastEmbed model")
except Exception as e:
    logger.error(f"Failed to initialize FastEmbed model: {e}")
    raise


@app.route('/search', methods=['POST'])
def search():
    """Search Qdrant for top N results based on query text"""
    try:
        data = request.get_json()
        if not data or 'query_text' not in data or 'top_n' not in data:
            return jsonify({"error": "Missing query_text or top_n in request body"}), 400

        query_text = data['query_text']
        top_n = int(data['top_n'])

        if not isinstance(query_text, str) or not query_text.strip():
            return jsonify({"error": "query_text must be a non-empty string"}), 400
        if top_n <= 0:
            return jsonify({"error": "top_n must be a positive integer"}), 400

        # Generate embedding for query text
        logger.info(f"Generating embedding for query: {query_text[:50]}...")
        query_embedding = list(embedding_model.embed([query_text]))[0].tolist()

        # Validate embedding
        if len(query_embedding) != 384:
            logger.error(f"Invalid query embedding length: {len(query_embedding)}")
            return jsonify({"error": "Failed to generate valid query embedding"}), 500

        # Search Qdrant
        logger.info(f"Searching Qdrant for top {top_n} results")
        search_results = qdrant_client.search(
            collection_name='test_collection',
            query_vector=query_embedding,
            limit=top_n,
            with_payload=True
        )

        # Format results
        results = [
            {
                "doc_id": result.payload.get("doc_id", ""),
                "chunk_id": result.id,
                "text": result.payload.get("text", ""),
                "score": float(result.score)
            }
            for result in search_results
        ]

        logger.info(f"Returning {len(results)} results")
        return jsonify({"results": results}), 200

    except Exception as e:
        logger.error(f"Search error: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)