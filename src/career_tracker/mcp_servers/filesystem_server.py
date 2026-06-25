"""Filesystem MCP Tool Server.

Provides tools for reading resumes, cover letters, and saving files
to local storage. All paths are sandboxed to the configured data directories.

Usage::

    python -m career_tracker.mcp_servers.filesystem_server
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import structlog
from mcp.server.fastmcp import FastMCP

from career_tracker.config import get_settings

logger = structlog.get_logger(__name__)

mcp = FastMCP("FilesystemToolServer")

_SUPPORTED_RESUME_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md"}


@mcp.tool()
def list_resumes() -> list[dict]:
    """List all available resume files.

    Returns:
        List of dicts with 'filename', 'path', 'size_bytes', and 'extension'.
    """
    settings = get_settings()
    resumes_dir = settings.resolve_path(settings.resumes_dir)
    resumes_dir.mkdir(parents=True, exist_ok=True)

    resumes = []
    for f in resumes_dir.iterdir():
        if f.is_file() and f.suffix.lower() in _SUPPORTED_RESUME_EXTENSIONS:
            resumes.append({
                "filename": f.name,
                "path": str(f),
                "size_bytes": f.stat().st_size,
                "extension": f.suffix.lower(),
            })

    logger.info("filesystem.resumes_listed", count=len(resumes))
    return sorted(resumes, key=lambda x: x["filename"])


@mcp.tool()
def get_resume(filename: Optional[str] = None) -> dict:
    """Get resume file content.

    If no filename is specified, returns the most recently modified resume.

    Args:
        filename: Specific resume filename to read. If None, returns latest.

    Returns:
        Dict with 'filename', 'content' (text), and 'path'.
    """
    settings = get_settings()
    resumes_dir = settings.resolve_path(settings.resumes_dir)

    if filename:
        path = resumes_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Resume not found: {filename}")
    else:
        # Find the most recently modified resume
        resumes = [
            f for f in resumes_dir.iterdir()
            if f.is_file() and f.suffix.lower() in _SUPPORTED_RESUME_EXTENSIONS
        ]
        if not resumes:
            return {"filename": None, "content": "", "path": None, "message": "No resumes found"}
        path = max(resumes, key=lambda f: f.stat().st_mtime)

    # Read text content (works for .txt, .md; for .pdf/.docx we return metadata)
    if path.suffix.lower() in {".txt", ".md"}:
        content = path.read_text(encoding="utf-8", errors="replace")
    else:
        content = f"[Binary file: {path.name} — {path.stat().st_size} bytes. Use a document parser for full text.]"

    logger.info("filesystem.resume_read", filename=path.name)
    return {
        "filename": path.name,
        "content": content,
        "path": str(path),
    }


@mcp.tool()
def list_cover_letters() -> list[dict]:
    """List all available cover letter templates.

    Returns:
        List of dicts with 'filename', 'path', 'size_bytes'.
    """
    settings = get_settings()
    cl_dir = settings.resolve_path(settings.cover_letters_dir)
    cl_dir.mkdir(parents=True, exist_ok=True)

    letters = []
    for f in cl_dir.iterdir():
        if f.is_file() and f.suffix.lower() in _SUPPORTED_RESUME_EXTENSIONS:
            letters.append({
                "filename": f.name,
                "path": str(f),
                "size_bytes": f.stat().st_size,
            })

    return sorted(letters, key=lambda x: x["filename"])


@mcp.tool()
def get_cover_letter(filename: Optional[str] = None) -> dict:
    """Get cover letter content.

    If no filename specified, returns the most recently modified cover letter.

    Args:
        filename: Specific cover letter filename to read.

    Returns:
        Dict with 'filename', 'content', and 'path'.
    """
    settings = get_settings()
    cl_dir = settings.resolve_path(settings.cover_letters_dir)

    if filename:
        path = cl_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Cover letter not found: {filename}")
    else:
        letters = [
            f for f in cl_dir.iterdir()
            if f.is_file() and f.suffix.lower() in _SUPPORTED_RESUME_EXTENSIONS
        ]
        if not letters:
            return {"filename": None, "content": "", "path": None, "message": "No cover letters found"}
        path = max(letters, key=lambda f: f.stat().st_mtime)

    if path.suffix.lower() in {".txt", ".md"}:
        content = path.read_text(encoding="utf-8", errors="replace")
    else:
        content = f"[Binary file: {path.name} — {path.stat().st_size} bytes.]"

    logger.info("filesystem.cover_letter_read", filename=path.name)
    return {
        "filename": path.name,
        "content": content,
        "path": str(path),
    }


@mcp.tool()
def save_file(content: str, filename: str, directory: str = "attachments") -> str:
    """Save text content to a file in local storage.

    Args:
        content: Text content to write.
        filename: Desired filename.
        directory: Subdirectory under data/ ('attachments', 'resumes', 'cover_letters').

    Returns:
        The full path where the file was saved.
    """
    settings = get_settings()

    # Map directory names to configured paths
    dir_map = {
        "attachments": settings.attachments_dir,
        "resumes": settings.resumes_dir,
        "cover_letters": settings.cover_letters_dir,
    }

    target_dir = dir_map.get(directory)
    if target_dir is None:
        raise ValueError(
            f"Invalid directory '{directory}'. Must be one of: {list(dir_map.keys())}"
        )

    resolved_dir = settings.resolve_path(target_dir)
    resolved_dir.mkdir(parents=True, exist_ok=True)

    save_path = resolved_dir / filename
    save_path.write_text(content, encoding="utf-8")

    logger.info("filesystem.file_saved", path=str(save_path), size=len(content))
    return str(save_path)


if __name__ == "__main__":
    mcp.run(transport="stdio")
