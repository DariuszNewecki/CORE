# src/features/introspection/graph_analysis_service.py

"""
Provides a service for finding semantic clusters of symbols in the codebase
using K-Means clustering on their vector embeddings.
"""

from __future__ import annotations

import numpy as np

from shared.infrastructure.clients.qdrant_client import QdrantService
from shared.logger import getLogger


try:
    from sklearn.cluster import KMeans
except ImportError:
    KMeans = None
logger = getLogger(__name__)


# ID: a38ed737-0757-4a63-9797-e55969255ce3
async def find_semantic_clusters(
    qdrant_service: QdrantService, n_clusters: int = 15
) -> list[list[str]]:
    """
    Finds clusters of semantically similar code symbols using K-Means clustering.
    """
    if KMeans is None:
        logger.error(
            "scikit-learn is not installed. Cannot perform clustering. Please run 'poetry install --with dev'."
        )
        return []
    logger.info("Finding %s semantic clusters using K-Means...", n_clusters)
    try:
        all_points = await qdrant_service.get_all_vectors()
        if not all_points:
            logger.warning("No vectors found in Qdrant. Cannot perform clustering.")
            return []
        vectors = []
        symbol_keys = []
        for point in all_points:
            if point.payload and "chunk_id" in point.payload and point.vector:
                symbol_keys.append(point.payload["chunk_id"])
                vectors.append(point.vector)
        if not vectors:
            logger.warning("No valid vectors with symbol payloads found.")
            return []
        logger.info("Clustering {len(vectors)} vectors into %s domains...", n_clusters)
        vector_array = np.array(vectors, dtype=np.float32)
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init="auto")
        labels = kmeans.fit_predict(vector_array)
        clusters: list[list[str]] = [[] for _ in range(n_clusters)]
        for i, label in enumerate(labels):
            clusters[label].append(symbol_keys[i])
        logger.info(f"Found {len(clusters)} semantic clusters.")
        clusters.sort(key=len, reverse=True)
        return [c for c in clusters if c]
    except Exception as e:
        logger.error(f"Failed to find semantic clusters: {e}", exc_info=True)
        return []
