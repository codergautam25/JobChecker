"""Service for handling the conversational AI agent and user queries."""

import json
import uuid

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from career_tracker.db.database import get_database
from career_tracker.db.repositories.user_profile_repo import UserProfileRepository
from career_tracker.llm.client import get_llm
from career_tracker.memory.store import USER_PREFERENCES, get_memory_store


@tool
def get_user_profile() -> str:
    """Fetch the user's detailed career profile, settings, skills, and past experience."""
    profile = UserProfileRepository().get_default()
    if not profile:
        return "No profile setup yet."

    parts = [f"Name: {profile.get('name', 'Unknown')}"]
    if profile.get('email'):
        parts.append(f"Email: {profile.get('email')}")
        
    skills = profile.get('skills')
    if skills:
        skills_list = json.loads(skills) if isinstance(skills, str) else skills
        parts.append(f"Skills: {', '.join(skills_list)}")
        
    roles = profile.get('target_roles')
    if roles:
        roles_list = json.loads(roles) if isinstance(roles, str) else roles
        parts.append(f"Roles: {', '.join(roles_list)}")
        
    return " | ".join(parts)


@tool
def remember_fact(fact: str) -> str:
    """Save a piece of conversational memory or fact about the user for future reference."""
    try:
        store = get_memory_store()
        store.save(
            collection=USER_PREFERENCES, 
            doc_id=str(uuid.uuid4()), 
            content=fact, 
            metadata={"source": "chat"}
        )
        return f"Successfully remembered: {fact}"
    except Exception as e:
        return f"Failed to remember fact: {e}"


@tool
def search_memory(query: str) -> str:
    """Search the conversational memory for past facts about the user."""
    try:
        store = get_memory_store()
        results = store.search(collection=USER_PREFERENCES, query=query, n_results=5)
        if not results:
            return "No relevant past facts found."
        return json.dumps([r['content'] for r in results])
    except Exception as e:
        return f"Failed to search memory: {e}"


@tool
def get_tracker_report() -> str:
    """Get statistics and details about tracked job applications, emails, and interview status."""
    try:
        db = get_database()
        app_rows = db.execute("SELECT status, COUNT(*) as count FROM applications GROUP BY status")
        app_stats = {r["status"]: r["count"] for r in app_rows}
        
        recent_apps = db.execute(
            "SELECT company, role, status FROM applications ORDER BY updated_at DESC LIMIT 5"
        )
        
        total = sum(app_stats.values())
        stats_str = ", ".join(f"{k}: {v}" for k, v in app_stats.items())
        recent_str = ", ".join(f"{r['company']} ({r['status']})" for r in recent_apps)
        
        return f"Total Apps: {total} | Status: {stats_str} | Recent: {recent_str}"
    except Exception as e:
        return f"Failed to get tracker report: {e}"


def handle_general_chat(message: str) -> str:
    """
    Process a user's chat message using a tool-enabled LLM agent.
    
    Args:
        message (str): The input message from the user.
        
    Returns:
        str: The final text response from the AI agent.
    """
    llm = get_llm()
    tools = [get_user_profile, remember_fact, search_memory, get_tracker_report]
    llm_with_tools = llm.bind_tools(tools)
    
    system_prompt = (
        "You are a personalized career AI assistant. The user is talking to you via a chat interface. "
        "You have tools to fetch their profile, remember facts they tell you, search memory, and get reports on their job application tracker. "
        "Use them to answer their questions accurately and helpfully."
    )
    
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=message)]
    response = llm_with_tools.invoke(messages)
    
    while response.tool_calls:
        messages.append(response)
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            
            tool_map = {
                "get_user_profile": get_user_profile,
                "remember_fact": remember_fact,
                "search_memory": search_memory,
                "get_tracker_report": get_tracker_report
            }
            
            tool_func = tool_map.get(tool_name)
            tool_res = tool_func.invoke(tool_args) if tool_func else "Tool not found."
                
            messages.append(ToolMessage(content=str(tool_res), tool_call_id=tool_call["id"]))
            
        response = llm_with_tools.invoke(messages)
        
    return str(response.content)
