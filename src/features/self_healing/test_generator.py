# src/features/self_healing/test_generator.py
"""
Thin wrapper that exposes the new modular test generation pipeline.
"""

from .test_generation.generator import EnhancedTestGenerator

__all__ = ["EnhancedTestGenerator"]
