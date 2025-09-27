from typing import List

import networkx as nx
from app.core.config import get_settings
from qdrant_client import QdrantClient
from qdrant_client.models import Filter


async def find_semantic_clusters(similarity_threshold: float = 0.85) -> List[List[str]]:
    """
    Find clusters of semantically similar code symbols using graph analysis.

    Args:
        similarity_threshold: Minimum cosine similarity for symbols to be connected

    Returns:
        List of clusters, where each cluster is a list of symbol keys
    """
    settings = get_settings()

    # Connect to Qdrant
    client = QdrantClient(url=settings.qdrant_url)

    # Scroll through all vectors in the collection
    all_vectors = []
    next_offset = None

    while True:
        scroll_response = client.scroll(
            collection_name=settings.qdrant_collection,
            scroll_filter=Filter(),
            offset=next_offset,
            limit=100,
        )

        all_vectors.extend(scroll_response[0])

        if not scroll_response[1]:
            break

        next_offset = scroll_response[1]

    if not all_vectors:
        return []

    # Build similarity graph
    graph = nx.Graph()

    # Add all symbols as nodes
    for vector in all_vectors:
        symbol_key = vector.payload.get("symbol_key")
        if symbol_key:
            graph.add_node(symbol_key, vector=vector.vector)

    # Calculate similarities and add edges
    nodes = list(graph.nodes(data=True))

    for i, (node1, data1) in enumerate(nodes):
        vector1 = data1["vector"]

        for j, (node2, data2) in enumerate(nodes[i + 1 :], i + 1):
            vector2 = data2["vector"]

            # Calculate cosine similarity
            dot_product = sum(a * b for a, b in zip(vector1, vector2))
            norm1 = sum(a * a for a in vector1) ** 0.5
            norm2 = sum(b * b for b in vector2) ** 0.5

            if norm1 == 0 or norm2 == 0:
                similarity = 0.0
            else:
                similarity = dot_product / (norm1 * norm2)

            # Add edge if similarity exceeds threshold
            if similarity >= similarity_threshold:
                graph.add_edge(node1, node2, weight=similarity)

    # Find connected components (clusters)
    clusters = list(nx.connected_components(graph))

    # Convert to list of lists
    result = [list(cluster) for cluster in clusters]

    return result
