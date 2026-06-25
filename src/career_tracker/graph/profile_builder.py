"""LangGraph workflow for dynamic profile building."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, TypedDict

import structlog
from langgraph.graph import END, StateGraph

from career_tracker.db.repositories.user_profile_repo import UserProfileRepository
from career_tracker.llm.client import get_structured_llm
from career_tracker.llm.prompts import EXTRACT_PROFILE_SYSTEM, EXTRACT_PROFILE_USER
from career_tracker.models.profile import ExtractedProfile

logger = structlog.get_logger(__name__)


class ProfileBuilderState(TypedDict):
    """State for the profile builder workflow."""
    file_path: Optional[str]
    raw_text: Optional[str]
    extracted_profile: Optional[ExtractedProfile]
    status: str
    error: Optional[str]


def parse_document_node(state: ProfileBuilderState) -> dict:
    """Read a document (PDF, DOCX, TXT) and extract raw text."""
    path_str = state.get("file_path")
    if not path_str:
        return {"error": "No file path provided."}
    
    path = Path(path_str)
    if not path.exists():
        return {"error": f"File not found: {path_str}"}
    
    ext = path.suffix.lower()
    text = ""
    
    try:
        if ext == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            for page in reader.pages:
                text += page.extract_text() + "\n"
        elif ext in {".docx", ".doc"}:
            import docx
            doc = docx.Document(str(path))
            for para in doc.paragraphs:
                text += para.text + "\n"
        else:
            # Fallback to plain text
            text = path.read_text(encoding="utf-8", errors="replace")
            
        logger.info("profile_builder.document_parsed", path=path.name, size=len(text))
        return {"raw_text": text}
    except Exception as e:
        logger.error("profile_builder.parse_failed", error=str(e))
        return {"error": str(e)}


def extract_profile_node(state: ProfileBuilderState) -> dict:
    """Use an LLM to extract profile data from raw text."""
    text = state.get("raw_text")
    if not text:
        return {"error": "No raw text to process."}

    # Truncate text if it's too long (e.g. 50k chars roughly 12k tokens)
    if len(text) > 50000:
        logger.warning("profile_builder.text_truncated")
        text = text[:50000]

    try:
        llm = get_structured_llm(ExtractedProfile)
        
        system_prompt = EXTRACT_PROFILE_SYSTEM
        user_prompt = EXTRACT_PROFILE_USER.format(text_content=text)
        
        result: ExtractedProfile = llm.invoke([
            ("system", system_prompt),
            ("user", user_prompt)
        ])
        
        logger.info("profile_builder.profile_extracted", name=result.name)
        return {"extracted_profile": result}
    except Exception as e:
        logger.error("profile_builder.extract_failed", error=str(e))
        return {"error": str(e)}


def _dedupe_list(old_list: list, new_list: list, key_fn) -> list:
    """Merge two lists of dicts, deduplicating by a key function."""
    seen = {key_fn(item): item for item in old_list}
    for item in new_list:
        seen[key_fn(item)] = item  # New items overwrite old ones if key matches
    return list(seen.values())


def merge_profile_node(state: ProfileBuilderState) -> dict:
    """Merge extracted profile into the SQLite database."""
    extracted = state.get("extracted_profile")
    if not extracted:
        return {"error": "No extracted profile to merge."}

    repo = UserProfileRepository()
    current_profile = repo.get_default()
    
    data = extracted.model_dump(exclude_none=True)
    
    if not current_profile:
        # Create a new profile if none exists
        from uuid import uuid4
        new_profile = {"id": str(uuid4()), "name": data.get("name") or "User", "email": data.get("email") or ""}
        current_profile = repo.create(new_profile)

    updates = {}
    
    # Simple scalar fields: update only if not empty
    scalar_fields = ["name", "email", "phone", "linkedin_url", "github_url", "portfolio_url"]
    for f in scalar_fields:
        if data.get(f):
            updates[f] = data[f]
            
    # List of strings: merge and deduplicate
    file_path_str = state.get("file_path")
    is_cv = False
    if file_path_str:
        is_cv = Path(file_path_str).name == "my_cv.pdf"

    list_str_fields = ["target_roles", "target_locations", "preferred_industries", "skills", "awards", "languages"]
    for f in list_str_fields:
        if data.get(f):
            if is_cv and f == "skills":
                continue
            existing = current_profile.get(f) or []
            merged = list(set(existing + data[f]))
            updates[f] = merged
            
    # List of dicts: deduplicate by specific keys
    if data.get("experience"):
        existing = current_profile.get("experience") or []
        # Key by company + role
        updates["experience"] = _dedupe_list(
            existing, data["experience"], 
            lambda x: f"{x.get('company', '')}_{x.get('role', '')}".lower()
        )
        
    if data.get("education"):
        existing = current_profile.get("education") or []
        updates["education"] = _dedupe_list(
            existing, data["education"], 
            lambda x: f"{x.get('institution', '')}_{x.get('degree', '')}".lower()
        )
        
    if data.get("certifications"):
        existing = current_profile.get("certifications") or []
        updates["certifications"] = _dedupe_list(
            existing, data["certifications"], 
            lambda x: str(x.get('name', '')).lower()
        )
        
    if data.get("projects"):
        existing = current_profile.get("projects") or []
        updates["projects"] = _dedupe_list(
            existing, data["projects"], 
            lambda x: str(x.get('name', '')).lower()
        )
        
    if data.get("publications"):
        existing = current_profile.get("publications") or []
        updates["publications"] = _dedupe_list(
            existing, data["publications"], 
            lambda x: str(x.get('title', '')).lower()
        )

    # Social Links (now a list of dicts)
    if data.get("social_links"):
        existing = current_profile.get("social_links") or []
        updates["social_links"] = _dedupe_list(
            existing, data["social_links"], 
            lambda x: str(x.get('platform', '')).lower()
        )
        
    # Append parsed file name
    file_path_str = state.get("file_path")
    if file_path_str:
        file_name = Path(file_path_str).name
        existing_files = current_profile.get("parsed_files") or []
        if file_name not in existing_files:
            updates["parsed_files"] = existing_files + [file_name]

    if updates:
        repo.update(current_profile["id"], updates)
        logger.info("profile_builder.merged", updates=list(updates.keys()))
        
    return {"status": "success"}


def route_after_parse(state: ProfileBuilderState) -> str:
    if state.get("error"):
        return END
    return "extract_profile"

def route_after_extract(state: ProfileBuilderState) -> str:
    if state.get("error"):
        return END
    return "merge_profile"

def build_profile_workflow() -> StateGraph:
    graph = StateGraph(ProfileBuilderState)
    
    graph.add_node("parse_document", parse_document_node)
    graph.add_node("extract_profile", extract_profile_node)
    graph.add_node("merge_profile", merge_profile_node)
    
    graph.set_entry_point("parse_document")
    
    graph.add_conditional_edges("parse_document", route_after_parse, {"extract_profile": "extract_profile", END: END})
    graph.add_conditional_edges("extract_profile", route_after_extract, {"merge_profile": "merge_profile", END: END})
    graph.add_edge("merge_profile", END)
    
    return graph.compile()
