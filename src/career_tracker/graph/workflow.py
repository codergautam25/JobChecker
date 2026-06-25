"""LangGraph workflow definition and compilation.

Assembles all nodes and edges into a compiled StateGraph with
SQLite-backed checkpointing and human-in-the-loop interrupts.

Usage::

    from career_tracker.graph.workflow import build_workflow, run_workflow

    # Build the graph once
    workflow = build_workflow()

    # Run a processing cycle
    result = run_workflow(workflow, thread_id="main")
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import structlog
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from career_tracker.config import get_settings
from career_tracker.graph.edges import (
    route_after_fetch,
    route_approval_decision,
    route_by_category,
)
from career_tracker.graph.nodes.classify_email import classify_email_node
from career_tracker.graph.nodes.draft_reply import draft_reply_node
from career_tracker.graph.nodes.error_recovery import error_recovery_node
from career_tracker.graph.nodes.extract_job_info import extract_job_info_node
from career_tracker.graph.nodes.extract_recruiter_info import extract_recruiter_info_node
from career_tracker.graph.nodes.fetch_emails import fetch_emails_node
from career_tracker.graph.nodes.human_approval import human_approval_node
from career_tracker.graph.nodes.ignore import ignore_node
from career_tracker.graph.nodes.interview import interview_node
from career_tracker.graph.nodes.rejection import rejection_node
from career_tracker.graph.nodes.send_reply import send_reply_node
from career_tracker.graph.nodes.store_application import store_application_node
from career_tracker.models.state import WorkflowState

logger = structlog.get_logger(__name__)


def _make_checkpointer():
    """Create a SQLite checkpointer, falling back to in-memory if needed."""
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
        settings = get_settings()
        checkpoint_path = settings.resolve_path(settings.db_path)
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(checkpoint_path), check_same_thread=False)
        return SqliteSaver(conn)
    except Exception as e:
        logger.warning("workflow.sqlite_checkpointer_failed", error=str(e))
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()


def build_workflow() -> CompiledStateGraph:
    """Build and compile the full Career Tracker workflow graph.

    Returns a compiled graph with:
    - SQLite checkpointing for persistence across restarts
    - interrupt_before on human_approval for human-in-the-loop
    - All 12 nodes wired with conditional routing
    """
    graph = StateGraph(WorkflowState)

    # ── Register all nodes ───────────────────────────────────────────────
    graph.add_node("fetch_emails", fetch_emails_node)
    graph.add_node("classify_email", classify_email_node)
    graph.add_node("extract_job_info", extract_job_info_node)
    graph.add_node("extract_recruiter_info", extract_recruiter_info_node)
    graph.add_node("draft_reply", draft_reply_node)
    graph.add_node("store_application", store_application_node)
    graph.add_node("human_approval", human_approval_node)
    graph.add_node("send_reply", send_reply_node)
    graph.add_node("interview", interview_node)
    graph.add_node("rejection", rejection_node)
    graph.add_node("ignore", ignore_node)
    graph.add_node("error_recovery", error_recovery_node)

    # ── Entry point ──────────────────────────────────────────────────────
    graph.set_entry_point("fetch_emails")

    # ── Edge: fetch_emails → classify or end ─────────────────────────────
    graph.add_conditional_edges(
        "fetch_emails",
        route_after_fetch,
        {
            "classify_email": "classify_email",
            "__end__": END,
        },
    )

    # ── Edge: classify → route by category ───────────────────────────────
    graph.add_conditional_edges(
        "classify_email",
        route_by_category,
        {
            "extract_job_info": "extract_job_info",
            "extract_recruiter_info": "extract_recruiter_info",
            "interview": "interview",
            "rejection": "rejection",
            "ignore": "ignore",
            "human_approval": "human_approval",
            "error_recovery": "error_recovery",
        },
    )

    # ── Extraction → Draft Reply ─────────────────────────────────────────
    graph.add_edge("extract_job_info", "draft_reply")
    graph.add_edge("extract_recruiter_info", "draft_reply")

    # ── Draft Reply → Store Application → Human Approval ─────────────────
    graph.add_edge("draft_reply", "store_application")
    graph.add_edge("store_application", "human_approval")

    # ── Interview / Rejection → Store Application ────────────────────────
    graph.add_edge("interview", "store_application")
    graph.add_edge("rejection", END)

    # ── Ignore → End ─────────────────────────────────────────────────────
    graph.add_edge("ignore", END)

    # ── Human Approval → route to send or end ────────────────────────────
    graph.add_conditional_edges(
        "human_approval",
        route_approval_decision,
        {
            "send_reply": "send_reply",
            "__end__": END,
        },
    )

    # ── Send Reply → End ─────────────────────────────────────────────────
    graph.add_edge("send_reply", END)

    # ── Error Recovery → End ─────────────────────────────────────────────
    graph.add_edge("error_recovery", END)

    # ── Compile with checkpointing ───────────────────────────────────────
    checkpointer = _make_checkpointer()

    compiled = graph.compile(
        checkpointer=checkpointer,
        # No interrupt_before — human_approval_node saves drafts to DB
        # and the UI loops to process all emails in one batch run.
    )

    logger.info("workflow.compiled", nodes=list(graph.nodes.keys()))

    return compiled


def run_workflow(
    workflow: CompiledStateGraph,
    thread_id: str = "main",
    initial_state: dict | None = None,
    log_fn=None,
) -> dict:
    """Execute a single email processing cycle.

    Args:
        workflow: The compiled LangGraph workflow.
        thread_id: Thread ID for checkpointing.
        initial_state: Optional initial state overrides.
        log_fn: Optional callable(str) for live progress updates.

    Returns:
        The full accumulated workflow state after execution.
    """
    config = {"configurable": {"thread_id": thread_id}}

    state = initial_state or {
        "emails": [],
        "current_email": None,
        "classification": None,
        "job_info": None,
        "recruiter_info": None,
        "interview_info": None,
        "draft_reply": None,
        "suggested_resume": None,
        "suggested_cover_letter": None,
        "pending_approvals": [],
        "processed_email_ids": [],
        "errors": [],
        "fetch_stats": None,
        "current_node": "start",
        "retry_count": 0,
        "should_continue": True,
    }

    logger.info("workflow.run.start", thread_id=thread_id)

    _LIST_KEYS = {"emails", "pending_approvals", "processed_email_ids", "errors"}
    accumulated = dict(state)

    # Human-readable labels for each node
    _NODE_LABELS = {
        "fetch_emails":           "Fetching emails from local database",
        "classify_email":         "Classifying email",
        "extract_job_info":       "Extracting job details",
        "extract_recruiter_info": "Extracting recruiter info",
        "draft_reply":            "Drafting reply",
        "store_application":      "Saving application to DB",
        "human_approval":         "Queuing draft for approval",
        "send_reply":             "Sending reply",
        "interview":              "Processing interview invite",
        "rejection":              "Processing rejection",
        "ignore":                 "Ignoring non-recruitment email",
        "error_recovery":         "Recovering from error",
    }

    def _emit(node_name: str, update: dict) -> None:
        """Fire log_fn with a human-readable progress line."""
        if not log_fn or node_name in ("__interrupt__", "__end__"):
            return
        label = _NODE_LABELS.get(node_name, node_name)
        detail = ""

        if node_name == "fetch_emails":
            stats = update.get("fetch_stats") or {}
            total  = stats.get("total_in_window", 0)
            new    = stats.get("new_emails", 0)
            skip   = stats.get("already_seen", 0)
            detail = f"  ({total} in window, {new} new, {skip} skipped)"

        elif node_name == "classify_email":
            clf   = update.get("classification") or {}
            email = accumulated.get("current_email") or {}
            subj  = (email.get("subject") or "")[:55]
            cat   = clf.get("category", "?")
            conf  = clf.get("confidence", 0)
            detail = f"  [{cat}  {conf:.0%}]  \"{subj}\""

        elif node_name == "human_approval":
            pending = update.get("pending_approvals") or []
            if pending:
                a     = pending[-1]
                draft = (a.get("payload") or {}).get("draft") or {}
                subj  = (draft.get("subject") or a.get("action_type", ""))[:55]
                detail = f"  \"{subj}\""

        elif node_name == "ignore":
            email = accumulated.get("current_email") or {}
            subj  = (email.get("subject") or "")[:55]
            detail = f"  \"{subj}\""

        # Use ASCII-safe output to avoid Windows charmap issues
        line = f"  {label}{detail}"
        try:
            log_fn(line)
        except UnicodeEncodeError:
            log_fn(line.encode("ascii", errors="replace").decode("ascii"))

    try:
        for event in workflow.stream(state, config):
            for node_name, update in event.items():
                logger.debug("workflow.run.node_complete", node=node_name)
                if not isinstance(update, dict):
                    continue
                # Emit progress BEFORE accumulating so we can read current_email from accumulated
                _emit(node_name, update)
                # Merge into accumulated state
                for k, v in update.items():
                    if k in _LIST_KEYS and isinstance(v, list):
                        accumulated[k] = (accumulated.get(k) or []) + v
                    else:
                        accumulated[k] = v
    except Exception as e:
        err_msg = str(e).encode("ascii", errors="replace").decode("ascii")
        logger.info("workflow.run.stopped", reason=err_msg)
        if log_fn:
            log_fn(f"  [stopped early: {err_msg[:80]}]")
        try:
            snapshot = workflow.get_state(config)
            if snapshot and snapshot.values:
                for k, v in snapshot.values.items():
                    if k not in accumulated or accumulated[k] is None:
                        accumulated[k] = v
        except Exception:
            pass

    logger.info("workflow.run.complete", thread_id=thread_id)
    return accumulated



def resume_workflow(
    workflow: CompiledStateGraph,
    thread_id: str = "main",
    approval_update: dict | None = None,
) -> dict:
    """Resume a workflow that was interrupted at human_approval.

    Args:
        workflow: The compiled LangGraph workflow.
        thread_id: The same thread_id used in the original run.
        approval_update: State update with the approval decision.

    Returns:
        The final workflow state after resumption.
    """
    config = {"configurable": {"thread_id": thread_id}}

    logger.info("workflow.resume", thread_id=thread_id)

    # Pass None to resume from the checkpoint
    result = None
    for event in workflow.stream(approval_update, config):
        for node_name, update in event.items():
            logger.debug("workflow.resume.node_complete", node=node_name)
            result = update

    logger.info("workflow.resume.complete", thread_id=thread_id)
    return result or {}
