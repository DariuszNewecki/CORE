# src/features/introspection/graph_analysis_service.py
"""
Provides a service for finding semantic clusters of symbols in the codebase
using K-Means clustering on their vector embeddings.
"""
from __future__ import annotations

from typing import List

import numpy as np
from rich.console import Console

# --- START OF FIX: Corrected imports ---
from services.clients.qdrant_client import QdrantService
from shared.logger import getLogger

try:
    from sklearn.cluster import KMeans
except ImportError:
    KMeans = None
# --- END OF FIX ---

log = getLogger("graph_analysis_service")
console = Console()


# ID: 1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d
async def find_semantic_clusters(
    n_clusters: int = 15,
) -> List[List[str]]:
    """
    Finds clusters of semantically similar code symbols using K-Means clustering.
    """
    if KMeans is None:
        log.error(
            "scikit-learn is not installed. Cannot perform clustering. "
            "Please run 'poetry install --with dev'."
        )
        return []

    log.info(f"Finding {n_clusters} semantic clusters using K-Means...")
    qdrant_service = QdrantService()

    try:
        all_points = await qdrant_service.get_all_vectors()
        if not all_points:
            log.warning("No vectors found in Qdrant. Cannot perform clustering.")
            return []

        # --- START OF FIX: Prepare data for K-Means ---
        vectors = []
        symbol_keys = []
        for point in all_points:
            if point.payload and "symbol" in point.payload and point.vector:
                symbol_keys.append(point.payload["symbol"])
                vectors.append(point.vector)

        if not vectors:
            log.warning("No valid vectors with symbol payloads found.")
            return []

        log.info(f"Clustering {len(vectors)} vectors into {n_clusters} domains...")
        vector_array = np.array(vectors, dtype=np.float32)

        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init="auto")
        labels = kmeans.fit_predict(vector_array)

        # Group symbol keys by their predicted cluster label
        clusters: List[List[str]] = [[] for _ in range(n_clusters)]
        for i, label in enumerate(labels):
            clusters[label].append(symbol_keys[i])
        # --- END OF FIX ---

        log.info(f"Found {len(clusters)} semantic clusters.")

        # Sort clusters by size, largest first, and remove empty ones
        clusters.sort(key=len, reverse=True)
        non_empty_clusters = [c for c in clusters if c]

        return non_empty_clusters

    except Exception as e:
        log.error(f"Failed to find semantic clusters: {e}", exc_info=True)
        return []
