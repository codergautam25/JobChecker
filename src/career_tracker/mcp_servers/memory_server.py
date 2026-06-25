"""Memory MCP Tool Server.

Exposes ChromaDB semantic memory operations as MCP tools.
Enables the LangGraph workflow to store and retrieve past interactions
for context-aware drafting and decision making.

Usage::

    python -m career_tracker.mcp_servers.memory_server
"""

from __future__ import annotations

from typing import Any, Optional

import structlog
from mcp.server.fastmcp import FastMCP

from career_tracker.memory.store import get_memory_store

logger = structlog.get_logger(__name__)

mcp = FastMCP("MemoryToolServer")


@mcp.tool()
def save_memory(
    collection: str,
    content: str,
    doc_id: str,
    metadata: Optional[dict[str, Any]] = None,
) -> str:
    """Save a document to semantic memory.

    Args:
        collection: Target collection name. One of:
            - 'approved_responses'
            - 'successful_applications'
            - 'recruiter_conversations'
            - 'interview_invitations'
        content: Text content to embed and store.
        doc_id: Unique document identifier.
        metadata: Optional key-value metadata for filtered retrieval.

    Returns:
        Confirmation message with the document ID.
    """
    store = get_memory_store()
    store.save(
        collection=collection,
        doc_id=doc_id,
        content=content,
        metadata=metadata or {},
    )
    return f"Saved document '{doc_id}' to collection '{collection}'."


@mcp.tool()
def search_memory(
    collection: str,
    query: str,
    n_results: int = 5,
    filters: Optional[dict[str, Any]] = None,
) -> list[dict]:
    """Search semantic memory for similar documents.

    Args:
        collection: Collection to search in.
        query: Natural language search query.
        n_results: Maximum number of results (default 5).
        filters: Optional ChromaDB where-clause for metadata filtering.
            Example: {"company": "Google"} to filter by company.

    Returns:
        List of matching documents with 'id', 'content', 'metadata', and 'distance'.
    """
    store = get_memory_store()
    results = store.search(
        collection=collection,
        query=query,
        n_results=n_results,
        filters=filters,
    )
    logger.info(
        "memory.searched",
        collection=collection,
        query=query[:50],
        results_count=len(results),
    )
    return results


@mcp.tool()
def delete_memory(collection: str, doc_id: str) -> str:
    """Delete a document from semantic memory.

    Args:
        collection: Collection containing the document.
        doc_id: ID of the document to delete.

    Returns:
        Confirmation message.
    """
    store = get_memory_store()
    store.delete(collection=collection, doc_id=doc_id)
    return f"Deleted document '{doc_id}' from collection '{collection}'."


@mcp.tool()
def get_memory_stats() -> dict[str, int]:
    """Get document counts for all memory collections.

    Returns:
        Dict mapping collection name to document count.
    """
    store = get_memory_store()
    from career_tracker.memory.store import _ALL_COLLECTIONS

    return {name: store.count(name) for name in _ALL_COLLECTIONS}


if __name__ == "__main__":
    mcp.run(transport="stdio")
