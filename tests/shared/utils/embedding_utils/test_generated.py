# src/shared/utils/embedding_utils.py
import unittest

import numpy as np

from shared.utils.embedding_utils import (
    calculate_cosine_similarity,
    compute_average_embedding,
    normalize_embeddings,
)


class TestEmbeddingUtils(unittest.TestCase):
    """Comprehensive tests for embedding_utils module."""

    def test_calculate_cosine_similarity_valid_inputs(self) -> None:
        """Test cosine similarity calculation with valid inputs."""
        vec1 = np.array([1.0, 0.0, 0.0])
        vec2 = np.array([0.0, 1.0, 0.0])
        result = calculate_cosine_similarity(vec1, vec2)
        self.assertAlmostEqual(result, 0.0, places=7)

        vec3 = np.array([1.0, 2.0, 3.0])
        vec4 = np.array([4.0, 5.0, 6.0])
        result = calculate_cosine_similarity(vec3, vec4)
        expected = np.dot(vec3, vec4) / (np.linalg.norm(vec3) * np.linalg.norm(vec4))
        self.assertAlmostEqual(result, expected, places=7)

    def test_calculate_cosine_similarity_identical_vectors(self) -> None:
        """Test cosine similarity with identical vectors."""
        vec = np.array([2.0, 3.0, 4.0])
        result = calculate_cosine_similarity(vec, vec)
        self.assertAlmostEqual(result, 1.0, places=7)

    def test_calculate_cosine_similarity_zero_vector(self) -> None:
        """Test cosine similarity with zero vector raises ValueError."""
        vec1 = np.array([0.0, 0.0, 0.0])
        vec2 = np.array([1.0, 2.0, 3.0])
        with self.assertRaises(ValueError):
            calculate_cosine_similarity(vec1, vec2)

    def test_calculate_cosine_similarity_dimension_mismatch(self) -> None:
        """Test cosine similarity with dimension mismatch raises ValueError."""
        vec1 = np.array([1.0, 2.0])
        vec2 = np.array([3.0, 4.0, 5.0])
        with self.assertRaises(ValueError):
            calculate_cosine_similarity(vec1, vec2)

    def test_normalize_embeddings_valid_input(self) -> None:
        """Test normalization of a single embedding."""
        embedding = np.array([3.0, 4.0])
        normalized = normalize_embeddings(embedding)
        expected = embedding / np.linalg.norm(embedding)
        np.testing.assert_array_almost_equal(normalized, expected)

    def test_normalize_embeddings_batch(self) -> None:
        """Test normalization of a batch of embeddings."""
        embeddings = np.array([[1.0, 0.0], [0.0, 2.0], [3.0, 4.0]])
        normalized = normalize_embeddings(embeddings)
        for i in range(embeddings.shape[0]):
            expected = embeddings[i] / np.linalg.norm(embeddings[i])
            np.testing.assert_array_almost_equal(normalized[i], expected)

    def test_normalize_embeddings_zero_norm(self) -> None:
        """Test normalization of zero vector raises ValueError."""
        embedding = np.array([0.0, 0.0, 0.0])
        with self.assertRaises(ValueError):
            normalize_embeddings(embedding)

    def test_compute_average_embedding_valid_input(self) -> None:
        """Test average embedding computation."""
        embeddings = [np.array([1.0, 2.0]), np.array([3.0, 4.0]), np.array([5.0, 6.0])]
        avg = compute_average_embedding(embeddings)
        expected = np.array([3.0, 4.0])
        np.testing.assert_array_almost_equal(avg, expected)

    def test_compute_average_embedding_empty_list(self) -> None:
        """Test average embedding with empty list raises ValueError."""
        with self.assertRaises(ValueError):
            compute_average_embedding([])

    def test_compute_average_embedding_dimension_mismatch(self) -> None:
        """Test average embedding with dimension mismatch raises ValueError."""
        embeddings = [np.array([1.0, 2.0]), np.array([3.0, 4.0, 5.0])]
        with self.assertRaises(ValueError):
            compute_average_embedding(embeddings)
