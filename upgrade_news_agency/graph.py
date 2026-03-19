from langgraph.graph import StateGraph, END

from state import NewsState
from tools import checkpointer, store
from agents import (
    planner_node,
    researcher_node,
    writer_node,
    fact_checker_node,
    editor_node,
    publisher_node,
    route_after_fact_check,
)

workflow = StateGraph(NewsState)

# ── Nodes ─────────────────────────────────────────────────────────────────────
workflow.add_node("planner",      planner_node)
workflow.add_node("researcher",   researcher_node)
workflow.add_node("writer",       writer_node)
workflow.add_node("fact_checker", fact_checker_node)
workflow.add_node("editor",       editor_node)
workflow.add_node("publisher",    publisher_node)

# ── Edges ─────────────────────────────────────────────────────────────────────
workflow.set_entry_point("planner")

workflow.add_edge("planner",    "researcher")
workflow.add_edge("researcher", "writer")
workflow.add_edge("writer",     "fact_checker")

# Conditional: fact_checker → writer (revise) OR editor (proceed)
workflow.add_conditional_edges(
    "fact_checker",
    route_after_fact_check,
    {
        "revise":  "writer",
        "proceed": "editor",
    },
)

workflow.add_edge("editor",    "publisher")
workflow.add_edge("publisher", END)

# ── Compile with short-term (checkpointer) + long-term (store) memory ─────────
# checkpointer  → MemorySaver  → persists thread state between steps
# store         → InMemoryStore → persists cross-thread data (topics, prefs, history)
graph = workflow.compile(
    checkpointer=checkpointer,
    store=store,
)