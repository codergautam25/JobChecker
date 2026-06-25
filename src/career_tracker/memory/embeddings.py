"""Embedding configuration for ChromaDB.

Provides a factory for the embedding function used across all
ChromaDB collections. Defaults to a local SentenceTransformers model
so no data leaves the user's machine.
"""

from __future__ import annotations

from functools import lru_cache

from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from career_tracker.config import get_settings


@lru_cache(maxsize=1)
def get_embedding_function() -> SentenceTransformerEmbeddingFunction:
    """Return a cached embedding function using the configured model.

    Default model: ``all-MiniLM-L6-v2`` — fast, small (80 MB), good
    for semantic similarity on short-to-medium text.
    """
    settings = get_settings()
    return SentenceTransformerEmbeddingFunction(
        model_name=settings.embedding_model,
    )
