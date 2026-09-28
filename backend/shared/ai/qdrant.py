import logging
import uuid
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import PointStruct, VectorParams, Distance, Filter, FieldCondition, MatchValue, FilterSelector
from backend.core.config import settings

logger = logging.getLogger("buildora.qdrant")

_qdrant_client: Optional[QdrantClient] = None

def get_qdrant_client() -> QdrantClient:
    """
    Initializes and returns a singleton QdrantClient.
    Supports remote URL/API Key or local in-memory storage for development/testing.
    """
    global _qdrant_client
    if _qdrant_client is None:
        if settings.QDRANT_URL:
            logger.info(f"Connecting to remote Qdrant server at: {settings.QDRANT_URL}")
            _qdrant_client = QdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY or None
            )
        else:
            logger.info("QDRANT_URL not configured. Using local in-memory Qdrant instance.")
            _qdrant_client = QdrantClient(location=":memory:")
    return _qdrant_client

def ensure_collection(
    collection_name: Optional[str] = None,
    vector_size: Optional[int] = None
) -> str:
    """
    Ensures that the specified Qdrant collection exists with the exact required vector dimension.
    If the collection exists with an incompatible vector dimension, raises a configuration error
    to prevent accidental deletion/recreation of the knowledge base.
    """
    client = get_qdrant_client()
    target_collection = collection_name or settings.QDRANT_COLLECTION_NAME
    expected_size = vector_size or settings.GEMINI_EMBEDDING_DIMENSION

    collections_response = client.get_collections()
    existing_names = [c.name for c in collections_response.collections]

    if target_collection not in existing_names:
        logger.info(f"Creating Qdrant collection '{target_collection}' with vector_size={expected_size}")
        client.create_collection(
            collection_name=target_collection,
            vectors_config=VectorParams(size=expected_size, distance=Distance.COSINE)
        )
    else:
        # Validate vector size of existing collection
        info = client.get_collection(collection_name=target_collection)
        existing_vectors_config = info.config.params.vectors
        
        # Handle single vs dict vector config
        if isinstance(existing_vectors_config, VectorParams):
            actual_size = existing_vectors_config.size
        elif isinstance(existing_vectors_config, dict) and "size" in existing_vectors_config:
            actual_size = existing_vectors_config["size"]
        elif hasattr(existing_vectors_config, "size"):
            actual_size = getattr(existing_vectors_config, "size")
        else:
            actual_size = expected_size  # Fallback

        if actual_size != expected_size:
            raise ValueError(
                f"Qdrant collection '{target_collection}' dimension mismatch: expected {expected_size}, "
                f"found {actual_size}. Automatic collection destruction is disabled."
            )

    return target_collection

def generate_deterministic_point_id(policy_document_id: int, chunk_index: int) -> str:
    """Generates a reproducible UUIDv5 for a chunk point based on policy ID and chunk index."""
    namespace = uuid.UUID("12345678-1234-5678-1234-567812345678")
    name = f"policy_{policy_document_id}_chunk_{chunk_index}"
    return str(uuid.uuid5(namespace, name))

def upsert_policy_chunks(
    points: List[Dict[str, Any]],
    collection_name: Optional[str] = None
) -> int:
    """
    Upserts chunk point vectors into Qdrant.
    Each point dict must contain:
    - id: str or int
    - vector: List[float]
    - payload: dict
    """
    if not points:
        return 0

    client = get_qdrant_client()
    target_collection = ensure_collection(collection_name)

    qdrant_points = [
        PointStruct(
            id=p["id"],
            vector=p["vector"],
            payload=p["payload"]
        )
        for p in points
    ]

    client.upsert(
        collection_name=target_collection,
        points=qdrant_points
    )
    logger.info(f"Upserted {len(qdrant_points)} points into Qdrant collection '{target_collection}'.")
    return len(qdrant_points)

def delete_policy_chunks_by_document_id(
    policy_document_id: int,
    collection_name: Optional[str] = None
) -> bool:
    """
    Deletes all Qdrant vector points associated with the specified policy_document_id.
    """
    try:
        client = get_qdrant_client()
        target_collection = collection_name or settings.QDRANT_COLLECTION_NAME

        collections_response = client.get_collections()
        existing_names = [c.name for c in collections_response.collections]
        if target_collection not in existing_names:
            return True

        client.delete(
            collection_name=target_collection,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="policy_document_id",
                            match=MatchValue(value=policy_document_id)
                        )
                    ]
                )
            )
        )
        logger.info(f"Deleted Qdrant points for policy_document_id={policy_document_id} from collection '{target_collection}'.")
        return True
    except Exception as e:
        logger.error(f"Error deleting Qdrant points for policy_document_id={policy_document_id}: {e}")
        return False

def delete_specific_qdrant_point_ids(
    point_ids: List[str],
    collection_name: Optional[str] = None
) -> bool:
    """
    Deletes a specific list of point IDs from Qdrant.
    Used during reindexing to remove stale chunks when a document shrinks.
    """
    if not point_ids:
        return True
    try:
        client = get_qdrant_client()
        target_collection = collection_name or settings.QDRANT_COLLECTION_NAME

        client.delete(
            collection_name=target_collection,
            points_selector=models.PointIdsList(points=point_ids)
        )
        logger.info(f"Deleted {len(point_ids)} stale points from collection '{target_collection}'.")
        return True
    except Exception as e:
        logger.error(f"Error deleting specific Qdrant point IDs: {e}")
        return False

def search_policy_chunks(
    query_vector: List[float],
    top_k: Optional[int] = None,
    score_threshold: Optional[float] = None,
    collection_name: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Searches Qdrant vector collection for policy chunks matching query_vector.
    Returns structured results containing metadata and relevance score.
    Do not return vectors or Qdrant internal point IDs to the frontend/LLM.
    """
    if not query_vector:
        return []

    client = get_qdrant_client()
    target_collection = ensure_collection(collection_name)

    limit = top_k if top_k is not None else settings.POLICY_RETRIEVAL_TOP_K
    threshold = score_threshold if score_threshold is not None else settings.POLICY_RETRIEVAL_SCORE_THRESHOLD

    try:
        if hasattr(client, "query_points"):
            res = client.query_points(
                collection_name=target_collection,
                query=query_vector,
                limit=limit,
                score_threshold=threshold,
            )
            hits = res.points if hasattr(res, "points") else res
        else:
            hits = client.search(
                collection_name=target_collection,
                query_vector=query_vector,
                limit=limit,
                score_threshold=threshold,
            )

        structured_results: List[Dict[str, Any]] = []
        for hit in hits:
            payload = hit.payload or {}
            structured_results.append({
                "policy_document_id": payload.get("policy_document_id"),
                "title": payload.get("title", ""),
                "category": payload.get("category", ""),
                "original_filename": payload.get("original_filename", ""),
                "page_number": payload.get("page_number"),
                "chunk_index": payload.get("chunk_index"),
                "text": payload.get("text", ""),
                "retrieval_score": round(float(hit.score), 4) if hit.score is not None else 0.0
            })

        logger.info(f"POLICY_RETRIEVAL qdrant search completed: found {len(structured_results)} chunks above threshold={threshold}")
        return structured_results
    except Exception as e:
        logger.error(f"POLICY_RETRIEVAL qdrant search failed: {e}", exc_info=True)
        return []
