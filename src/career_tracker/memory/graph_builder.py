"""
Backend API for constructing the Memory Knowledge Graph.
Pulls from SQLite (relational data) and ChromaDB (unstructured memory).
"""
import json
from typing import Dict, Any, List

from career_tracker.services import _get_db
from career_tracker.memory.store import get_memory_store, _ALL_COLLECTIONS

def build_knowledge_graph() -> Dict[str, Any]:
    nodes = []
    links = []
    
    # Extract ChromaDB Memory Collections as independent main sectors
    store = get_memory_store()
    for coll_name in _ALL_COLLECTIONS:
        try:
            coll = store._get_collection(coll_name)
            # Limit to 15 fragments per collection to keep the graph load instantaneous and readable
            data = coll.get(limit=15)
            
            # ALWAYS create a cluster hub for this collection so the 6 main sectors are always visible
            hub_id = f"hub_{coll_name}"
            nodes.append({
                "id": hub_id,
                "name": coll_name.replace("_", " ").title(),
                "val": 10,
                "type": "Memory Cluster",
                "color": "#f43f5e", # Rose
                "details": f"Memory Sector: {coll_name}"
            })
            
            if data and data.get("ids") and len(data["ids"]) > 0:
                for i in range(len(data["ids"])):
                    mem_id = data["ids"][i]
                    content = data["documents"][i] if "documents" in data and data["documents"] else "No content"
                    
                    # Make name readable instead of just "Memory Fragment"
                    short_name = content[:25].strip() + "..." if len(content) > 25 else content
                    
                    nodes.append({
                        "id": f"mem_{mem_id}",
                        "name": short_name,
                        "val": 4,
                        "type": "Memory Fragment",
                        "color": "#10b981", # Emerald
                        "details": content
                    })
                    # Link fragment to its sector hub
                    links.append({"source": hub_id, "target": f"mem_{mem_id}"})
        except Exception as e:
            print(f"Error pulling chroma collection {coll_name}:", e)
            
    return {"nodes": nodes, "links": links}
