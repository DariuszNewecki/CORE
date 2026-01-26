# src/features/introspection/semantic_clusterer.py

"""
Performs semantic clustering on exported capability vectors to discover data-driven domains.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

from shared.config import settings
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger


try:
    from sklearn.cluster import KMeans
except ImportError:
    KMeans = None
logger = getLogger(__name__)


# ID: 68884117-d8b0-4f04-ab01-61e0306c7e59
class SemanticClusteringError(RuntimeError):
    """Raised when semantic clustering cannot complete."""

    def __init__(self, message: str, *, exit_code: int = 1):
        super().__init__(message)
        self.exit_code = exit_code


# ID: 41c7d272-0d0d-4d84-9d99-984e9a698bd2
def run_clustering(input_path: Path | str, output: Path | str, n_clusters: int) -> None:
    """
    Loads exported vectors, runs K-Means clustering, and saves the proposed
    capability-to-domain mappings to a JSON file.
    """
    if KMeans is None:
        logger.error("scikit-learn is not installed. Aborting.")
        raise SemanticClusteringError(
            "scikit-learn is not installed for clustering.", exit_code=1
        )
    input_path = Path(input_path)
    output_path = Path(output)

    logger.info("Starting semantic clustering process...")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("   -> Loading vectors from %s...", input_path)
    vectors = []
    capability_keys = []
    try:
        with input_path.open("r", encoding="utf-8") as f:
            for line in f:
                record = json.loads(line)
                if "vector" in record and "payload" in record:
                    if "symbol" in record["payload"]:
                        vectors.append(record["vector"])
                        capability_keys.append(record["payload"]["symbol"])
    except FileNotFoundError as exc:
        logger.error("Input file not found: %s", input_path)
        raise SemanticClusteringError("Input file not found.", exit_code=1) from exc

    if not vectors:
        logger.error("No valid vector data found in %s.", input_path)
        raise SemanticClusteringError(
            f"No valid vector data found in {input_path}.", exit_code=1
        )
    logger.info(
        "   -> Loaded %s vectors for clustering into %s domains.",
        len(vectors),
        n_clusters,
    )
    X = np.array(vectors)
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init="auto")
    kmeans.fit(X)
    labels = kmeans.labels_
    proposed_domains = {
        key: f"domain_{label}"
        for key, label in zip(capability_keys, labels, strict=False)
    }
    file_handler = FileHandler()
    rel_path = str(output_path.relative_to(settings.REPO_PATH))
    file_handler.write_runtime_json(rel_path, proposed_domains)
    logger.info(
        "Successfully generated domain proposals for %s capabilities and saved to %s",
        len(proposed_domains),
        output_path,
    )


if __name__ == "__main__":
    import argparse

    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Run semantic clustering on exported capability vectors."
    )
    parser.add_argument(
        "input_path",
        type=Path,
        help="Path to the JSONL file containing exported vectors.",
    )
    parser.add_argument(
        "output",
        type=Path,
        help="Path to write the proposed domain mapping JSON file.",
    )
    parser.add_argument(
        "n_clusters",
        type=int,
        help="Number of clusters (domains) to produce.",
    )

    args = parser.parse_args()

    try:
        run_clustering(args.input_path, args.output, args.n_clusters)
    except SemanticClusteringError as exc:
        raise SystemExit(exc.exit_code) from exc
