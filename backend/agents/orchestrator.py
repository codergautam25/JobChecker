import os
from typing import TypedDict, List, Optional
from langgraph.graph import StateGraph, END
from backend.database import get_job_by_id, update_job_status, create_draft, get_latest_profile
from backend.agents.matcher import match_job_with_ollama, generate_email_response

# Define the state variables in our LangGraph state machine
class AgentFlowState(TypedDict):
    job_id: int
    title: str
    company: str
    description: str
    deep_link: str
    match_percentage: int
    probability_tier: str
    skill_gaps: List[str]
    email_draft_id: Optional[int]
    status: str

def match_job_node(state: AgentFlowState) -> AgentFlowState:
    """Evaluates the match using the local Ollama instance or fallback rules."""
    print(f"[Orchestrator] Running Match Node for Job ID: {state['job_id']}")
    
    match_pct, tier, gaps = match_job_with_ollama(
        state["title"],
        state["company"],
        state["description"]
    )
    
    # Save results to SQLite
    from backend.database import update_job_match
    update_job_match(state["job_id"], match_pct, tier, gaps, status="matched")
    
    return {
        **state,
        "match_percentage": match_pct,
        "probability_tier": tier,
        "skill_gaps": gaps,
        "status": "matched"
    }

def filter_routing_fn(state: AgentFlowState) -> str:
    """Decides if the job fits requirements or should be ignored."""
    # Filter: matches below 50% or Low probability are ignored
    if state["match_percentage"] < 50 or state["probability_tier"] == "Low":
        print(f"[Orchestrator] Job fit too low ({state['match_percentage']}%). Routing to IGNORE.")
        return "ignore"
    print(f"[Orchestrator] Job fit good ({state['match_percentage']}%). Routing to DRAFT.")
    return "draft"

def ignore_job_node(state: AgentFlowState) -> AgentFlowState:
    """Transitions the job to the ignored state in DB."""
    print(f"[Orchestrator] Running Ignore Node for Job ID: {state['job_id']}")
    update_job_status(state["job_id"], "ignored")
    return {**state, "status": "ignored"}

def draft_response_node(state: AgentFlowState) -> AgentFlowState:
    """Generates email drafts and queues them in SQLite for user review."""
    print(f"[Orchestrator] Running Draft Response Node for Job ID: {state['job_id']}")
    
    # We simulate receiving a contact template or generate a generic screening reply
    subject, body = generate_email_response(
        state["job_id"],
        "hr@company.com", # Mock recruiter
        f"Regarding your application at {state['company']}",
        f"Hi, we saw your profile. Let us know if you are interested in the {state['title']} role."
    )
    
    # Save the draft to database
    draft_id = create_draft(
        state["job_id"],
        recipient_email="recruiter@company.com",
        subject=subject,
        body=body
    )
    
    # Update job state in SQLite
    update_job_status(state["job_id"], "draft_generated")
    
    return {
        **state,
        "email_draft_id": draft_id,
        "status": "draft_generated"
    }

def submit_application_node(state: AgentFlowState) -> AgentFlowState:
    """Launches the Playwright submitter agent (runs after user approval)."""
    print(f"[Orchestrator] Running Submit Application Node for Job ID: {state['job_id']}")
    
    # In a real workflow, we launch submitter.py here
    # For state progression:
    update_job_status(state["job_id"], "applied")
    return {**state, "status": "applied"}


# Build the Graph
workflow = StateGraph(AgentFlowState)

# Add Node definitions
workflow.add_node("match_job", match_job_node)
workflow.add_node("ignore_job", ignore_job_node)
workflow.add_node("draft_response", draft_response_node)
workflow.add_node("submit_application", submit_application_node)

# Set Entrypoint
workflow.set_entry_point("match_job")

# Add Conditional Routing
workflow.add_conditional_edges(
    "match_job",
    filter_routing_fn,
    {
        "ignore": "ignore_job",
        "draft": "draft_response"
    }
)

# Connect final states
workflow.add_edge("ignore_job", END)
workflow.add_edge("draft_response", END)
workflow.add_edge("submit_application", END)

# Compile
app_flow = workflow.compile()

def process_scraped_job(job_id: int):
    """Entry point to process a scraped job database entry through LangGraph."""
    job = get_job_by_id(job_id)
    if not job:
        print(f"[Orchestrator] Error: Job ID {job_id} not found.")
        return None
        
    initial_state = AgentFlowState(
        job_id=job["id"],
        title=job["title"],
        company=job["company"],
        description=job["description"],
        deep_link=job["deep_link"],
        match_percentage=0,
        probability_tier="Low",
        skill_gaps=[],
        email_draft_id=None,
        status="scraped"
    )
    
    # Run the graph
    print(f"[Orchestrator] Running pipeline for scraped Job: {job['title']} at {job['company']}")
    final_state = app_flow.invoke(initial_state)
    return final_state

if __name__ == "__main__":
    # Test execution
    from backend.database import init_db, insert_job
    init_db()
    
    job_id = insert_job(
        title="Python Developer",
        company="Mock Tech Inc",
        description="Looking for Python Developer with FastAPI expertise. Docker is required.",
        deep_link="https://mocktech.com/jobs/123"
    )
    
    if job_id:
        process_scraped_job(job_id)
        print("LangGraph run completed successfully.")
