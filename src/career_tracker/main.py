"""Career Tracker -- Main entry point and CLI runner.

Provides a command-line interface for:
- Running the email processing workflow
- Managing the approval queue
- Viewing application status
- Initializing the system

Usage::

    # Initialize the system (first run)
    career-tracker init

    # Run a single email processing cycle
    career-tracker run

    # Run in continuous polling mode
    career-tracker watch

    # View pending approvals
    career-tracker approvals

    # Approve or reject an action
    career-tracker approve <approval_id>
    career-tracker reject <approval_id>

    # View applications
    career-tracker apps
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import structlog

from career_tracker.config import get_settings, PROJECT_ROOT
from career_tracker.utils.logging import setup_logging

logger = structlog.get_logger(__name__)


def cmd_init(args: argparse.Namespace) -> None:
    """Initialize the Career Tracker system."""
    print("[*] Initializing Career Tracker...")

    settings = get_settings()
    settings.ensure_directories()
    print("  [OK] Data directories created")

    # Initialize database
    from career_tracker.db.database import get_database
    db = get_database()
    print(f"  [OK] Database initialized at {settings.resolve_path(settings.db_path)}")

    # Initialize ChromaDB
    from career_tracker.memory.store import get_memory_store
    store = get_memory_store()
    print(f"  [OK] ChromaDB initialized at {settings.resolve_path(settings.chroma_path)}")

    # Check for Gmail credentials
    creds_path = settings.resolve_path(settings.gmail_credentials_path)
    if creds_path.exists():
        print("  [OK] Gmail credentials found")
    else:
        print(f"  [!!] Gmail credentials NOT found at {creds_path}")
        print("       Download credentials.json from Google Cloud Console")

    # Check for .env file
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        print("  [OK] .env file found")
    else:
        print("  [!!] .env file NOT found -- copy .env.example to .env and configure")

    print("\n[DONE] Initialization complete!")


def cmd_run(args: argparse.Namespace) -> None:
    """Run a single email processing cycle."""
    print("[*] Running email processing cycle...")

    from career_tracker.graph.workflow import build_workflow, run_workflow

    workflow = build_workflow()
    thread_id = f"run-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

    result = run_workflow(workflow, thread_id=thread_id)

    # Report results
    processed = result.get("processed_email_ids", []) if result else []
    errors = result.get("errors", []) if result else []
    pending = result.get("pending_approvals", []) if result else []

    print(f"\n[Results]")
    print(f"  Emails processed:  {len(processed)}")
    print(f"  Pending approvals: {len(pending)}")
    print(f"  Errors:            {len(errors)}")

    if pending:
        print("\n[Pending Approvals]")
        for approval in pending:
            print(f"  [{approval.get('id', '?')[:8]}] "
                  f"{approval.get('action_type', '?')} -- "
                  f"Status: {approval.get('status', '?')}")

    if errors:
        print("\n[Errors]")
        for error in errors:
            print(f"  [{error.get('node', '?')}] "
                  f"{error.get('error_type', '?')}: {error.get('message', '')[:100]}")


def cmd_watch(args: argparse.Namespace) -> None:
    """Run in continuous polling mode."""
    settings = get_settings()
    interval = args.interval or settings.email_poll_interval_seconds

    print(f"[*] Watching for new emails (polling every {interval}s)...")
    print("    Press Ctrl+C to stop.\n")

    from career_tracker.graph.workflow import build_workflow, run_workflow

    workflow = build_workflow()
    cycle = 0

    try:
        while True:
            cycle += 1
            thread_id = f"watch-{cycle}-{datetime.utcnow().strftime('%H%M%S')}"
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Cycle {cycle}...")

            try:
                result = run_workflow(workflow, thread_id=thread_id)
                processed = result.get("processed_email_ids", []) if result else []
                if processed:
                    print(f"  -> Processed {len(processed)} email(s)")
                else:
                    print(f"  -> No new emails")
            except Exception as e:
                print(f"  [ERROR] {e}")

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n\nStopped watching.")


def cmd_approvals(args: argparse.Namespace) -> None:
    """View pending approval queue."""
    from career_tracker.mcp_servers.database_server import get_pending_approvals

    pending = get_pending_approvals()

    if not pending:
        print("[OK] No pending approvals.")
        return

    print(f"\n[Pending Approvals ({len(pending)})]\n")
    for i, item in enumerate(pending, 1):
        payload = item.get("payload", {})
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                pass

        draft = payload.get("draft", {}) if isinstance(payload, dict) else {}

        print(f"  {i}. [{item.get('id', '?')[:8]}...]")
        print(f"     Type:    {item.get('action_type', '?')}")
        print(f"     Created: {item.get('created_at', '?')}")
        if draft:
            print(f"     To:      {draft.get('to', '?')}")
            print(f"     Subject: {draft.get('subject', '?')}")
            print(f"     Body:    {draft.get('body', '')[:100]}...")
        print()


def cmd_approve(args: argparse.Namespace) -> None:
    """Approve a pending action."""
    from career_tracker.mcp_servers.database_server import review_approval

    result = review_approval(
        approval_id=args.approval_id,
        decision="APPROVED",
        notes=args.notes,
    )
    print(f"[APPROVED] {result.get('id', args.approval_id)}")

    # Optionally resume the workflow to send the email
    if result.get("action_type") == "send_email":
        print("[*] Resuming workflow to send email...")
        from career_tracker.graph.workflow import build_workflow, resume_workflow
        workflow = build_workflow()
        resume_workflow(workflow, thread_id="main")
        print("[OK] Email sent!")


def cmd_reject(args: argparse.Namespace) -> None:
    """Reject a pending action."""
    from career_tracker.mcp_servers.database_server import review_approval

    result = review_approval(
        approval_id=args.approval_id,
        decision="REJECTED",
        notes=args.notes,
    )
    print(f"[REJECTED] {result.get('id', args.approval_id)}")


def cmd_apps(args: argparse.Namespace) -> None:
    """View tracked applications."""
    from career_tracker.db.repositories import ApplicationRepository

    repo = ApplicationRepository()

    if args.status:
        from career_tracker.models.application import ApplicationStatus
        apps = repo.get_by_status(ApplicationStatus(args.status.upper()))
    else:
        apps = repo.get_all(limit=args.limit)

    if not apps:
        print("No applications tracked yet.")
        return

    print(f"\n[Applications ({len(apps)})]\n")
    for app in apps:
        status_label = {
            "DISCOVERED": "[DISCOVERED]",
            "APPLIED":    "[APPLIED]   ",
            "SCREENING":  "[SCREENING] ",
            "INTERVIEWING": "[INTERVIEW] ",
            "OFFER":      "[OFFER]     ",
            "REJECTED":   "[REJECTED]  ",
            "WITHDRAWN":  "[WITHDRAWN] ",
        }.get(app.status.value, "[UNKNOWN]   ")

        print(f"  {status_label} {app.company} -- {app.role}")
        print(f"     Updated: {app.updated_at.strftime('%Y-%m-%d')}")
        if app.location:
            print(f"     Location: {app.location}")
        print()


def main() -> None:
    """Main CLI entry point."""
    # Ensure stdout uses UTF-8 on Windows to avoid codec errors
    import sys, io
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    parser = argparse.ArgumentParser(
        prog="career-tracker",
        description="Career Tracker -- Local-first AI Job Application Assistant",
    )
    parser.add_argument(
        "--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init
    subparsers.add_parser("init", help="Initialize the Career Tracker system")

    # run
    subparsers.add_parser("run", help="Run a single email processing cycle")

    # watch
    watch_parser = subparsers.add_parser("watch", help="Run in continuous polling mode")
    watch_parser.add_argument(
        "--interval", type=int, default=None,
        help="Polling interval in seconds (default: from config)",
    )

    # approvals
    subparsers.add_parser("approvals", help="View pending approvals")

    # approve
    approve_parser = subparsers.add_parser("approve", help="Approve a pending action")
    approve_parser.add_argument("approval_id", help="Approval ID to approve")
    approve_parser.add_argument("--notes", default=None, help="Optional reviewer notes")

    # reject
    reject_parser = subparsers.add_parser("reject", help="Reject a pending action")
    reject_parser.add_argument("approval_id", help="Approval ID to reject")
    reject_parser.add_argument("--notes", default=None, help="Optional rejection reason")

    # apps
    apps_parser = subparsers.add_parser("apps", help="View tracked applications")
    apps_parser.add_argument("--status", default=None, help="Filter by status")
    apps_parser.add_argument("--limit", type=int, default=50, help="Max results")

    args = parser.parse_args()

    # Setup logging
    setup_logging(level=args.log_level)

    # Route to command
    commands = {
        "init": cmd_init,
        "run": cmd_run,
        "watch": cmd_watch,
        "approvals": cmd_approvals,
        "approve": cmd_approve,
        "reject": cmd_reject,
        "apps": cmd_apps,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
