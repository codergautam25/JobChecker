"""ChromaDB semantic memory store.

Manages four persistent collections for recruitment intelligence:

- **approved_responses**: Successful reply templates with outcome metadata.
- **successful_applications**: Applications that progressed in the pipeline.
- **recruiter_conversations**: Full recruiter email thread context.
- **interview_invitations**: Interview scheduling patterns and prep notes.

All data persists to disk under ``data/chroma/`` — fully local, no network.
"""

from __future__ import annotations

from typing import Any, Optional

import chromadb
import structlog

from career_tracker.config import get_settings
from career_tracker.memory.embeddings import get_embedding_function

logger = structlog.get_logger(__name__)

# Collection names
APPROVED_RESPONSES = "approved_responses"
SUCCESSFUL_APPLICATIONS = "successful_applications"
RECRUITER_CONVERSATIONS = "recruiter_conversations"
INTERVIEW_INVITATIONS = "interview_invitations"
USER_PREFERENCES = "user_preferences"
AGENTIC_AUTOMATION = "agentic_automation"

_ALL_COLLECTIONS = [
    APPROVED_RESPONSES,
    SUCCESSFUL_APPLICATIONS,
    RECRUITER_CONVERSATIONS,
    INTERVIEW_INVITATIONS,
    USER_PREFERENCES,
    AGENTIC_AUTOMATION,
]


class MemoryStore:
    """Semantic memory store backed by ChromaDB with local persistence.

    Usage::

        store = MemoryStore()

        # Save a document
        store.save(
            collection="approved_responses",
            doc_id="abc-123",
            content="Thank you for reaching out about the SWE role...",
            metadata={"company": "Google", "role": "SWE", "outcome": "interview"},
        )

        # Search for similar documents
        results = store.search(
            collection="approved_responses",
            query="recruiter outreach for software engineer",
            n_results=3,
        )
    """

    def __init__(self) -> None:
        settings = get_settings()
        chroma_path = settings.resolve_path(settings.chroma_path)
        chroma_path.mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(path=str(chroma_path))
        self._embedding_fn = get_embedding_function()
        self._collections: dict[str, chromadb.Collection] = {}

        # Eagerly create or load all collections
        for name in _ALL_COLLECTIONS:
            self._collections[name] = self._client.get_or_create_collection(
                name=name,
                embedding_function=self._embedding_fn,
            )

        logger.info(
            "memory_store.initialized",
            path=str(chroma_path),
            collections=_ALL_COLLECTIONS,
        )

    def _get_collection(self, collection_name: str) -> chromadb.Collection:
        """Get a collection by name, raising ValueError if unknown."""
        if collection_name not in self._collections:
            raise ValueError(
                f"Unknown collection '{collection_name}'. "
                f"Valid collections: {_ALL_COLLECTIONS}"
            )
        return self._collections[collection_name]

    def save(
        self,
        collection: str,
        doc_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Save a document to a semantic memory collection.

        Args:
            collection: Name of the target collection.
            doc_id: Unique document identifier.
            content: Text content to embed and store.
            metadata: Key-value metadata for filtered retrieval.
        """
        coll = self._get_collection(collection)

        # ChromaDB metadata values must be str, int, float, or bool
        clean_metadata = self._sanitize_metadata(metadata) if metadata else {}

        coll.upsert(
            ids=[doc_id],
            documents=[content],
            metadatas=[clean_metadata],
        )
        logger.info(
            "memory.saved",
            collection=collection,
            doc_id=doc_id,
            content_length=len(content),
        )

    def search(
        self,
        collection: str,
        query: str,
        n_results: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search a collection using semantic similarity.

        Args:
            collection: Name of the collection to search.
            query: Natural language search query.
            n_results: Maximum number of results to return.
            filters: ChromaDB where-clause for metadata filtering.

        Returns:
            List of result dicts with 'id', 'content', 'metadata', and 'distance'.
        """
        coll = self._get_collection(collection)

        kwargs: dict[str, Any] = {
            "query_texts": [query],
            "n_results": min(n_results, coll.count() or n_results),
        }
        if filters:
            kwargs["where"] = filters

        # Skip search if collection is empty
        if coll.count() == 0:
            return []

        results = coll.query(**kwargs)

        # Flatten ChromaDB's nested result structure
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        ids = results.get("ids", [[]])[0]
        distances = results.get("distances", [[]])[0]

        return [
            {
                "id": doc_id,
                "content": doc,
                "metadata": meta,
                "distance": dist,
            }
            for doc_id, doc, meta, dist in zip(ids, documents, metadatas, distances)
        ]

    def delete(self, collection: str, doc_id: str) -> None:
        """Delete a document from a collection."""
        coll = self._get_collection(collection)
        coll.delete(ids=[doc_id])
        logger.info("memory.deleted", collection=collection, doc_id=doc_id)

    def count(self, collection: str) -> int:
        """Return the number of documents in a collection."""
        return self._get_collection(collection).count()

    @staticmethod
    def _sanitize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
        """Ensure all metadata values are ChromaDB-compatible types.

        ChromaDB only accepts str, int, float, or bool values.
        Lists and complex objects are JSON-serialized to strings.
        None values are dropped.
        """
        import json

        clean: dict[str, Any] = {}
        for key, value in metadata.items():
            if value is None:
                continue
            elif isinstance(value, (str, int, float, bool)):
                clean[key] = value
            elif isinstance(value, (list, dict)):
                clean[key] = json.dumps(value)
            else:
                clean[key] = str(value)
        return clean


# ── Module-level singleton ───────────────────────────────────────────────────

_memory_store: MemoryStore | None = None


def get_memory_store() -> MemoryStore:
    """Return a cached singleton MemoryStore."""
    global _memory_store
    if _memory_store is None:
        _memory_store = MemoryStore()
    return _memory_store
