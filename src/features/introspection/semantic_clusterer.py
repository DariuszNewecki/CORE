# src/features/introspection/semantic_clusterer.py

"""
Performs semantic clustering on exported capability vectors to discover data-driven domains.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import typer
from dotenv import load_dotenv

from shared.logger import getLogger

try:
    from sklearn.cluster import KMeans
except ImportError:
    KMeans = None
logger = getLogger(__name__)
app = typer.Typer(
    help="Export vector data from Qdrant for semantic analysis.", add_completion=False
)


# ID: 106bb2e2-15d6-42db-abc0-6b05d280b053
def run_clustering(input_path: Path, output: Path, n_clusters: int):
    """
    Loads exported vectors, runs K-Means clustering, and saves the proposed
    capability-to-domain mappings to a JSON file.
    """
    if KMeans is None:
        logger.error("scikit-learn is not installed. Aborting.")
        raise RuntimeError("scikit-learn is not installed for clustering.")
    logger.info("🚀 Starting semantic clustering process...")
    output.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"   -> Loading vectors from {input_path}...")
    vectors = []
    capability_keys = []
    with input_path.open("r", encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)
            if "vector" in record and "payload" in record:
                if "symbol" in record["payload"]:
                    vectors.append(record["vector"])
                    capability_keys.append(record["payload"]["symbol"])
    if not vectors:
        logger.error(f"❌ No valid vector data found in {input_path}.")
        raise ValueError(f"No valid vector data found in {input_path}.")
    logger.info(
        f"   -> Loaded {len(vectors)} vectors for clustering into {n_clusters} domains."
    )
    X = np.array(vectors)
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init="auto")
    kmeans.fit(X)
    labels = kmeans.labels_
    proposed_domains = {
        key: f"domain_{label}"
        for key, label in zip(capability_keys, labels, strict=False)
    }
    with output.open("w", encoding="utf-8") as f:
        json.dump(proposed_domains, f, indent=2, sort_keys=True)
    logger.info(
        f"✅ Successfully generated domain proposals for {len(proposed_domains)} capabilities and saved to {output}"
    )


if __name__ == "__main__":
    load_dotenv()
    typer.run(run_clustering)
