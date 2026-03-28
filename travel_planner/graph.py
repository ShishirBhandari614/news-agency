from langgraph.graph import StateGraph, END

from state import TravelState
from tools import checkpointer, store
from agents import (
    planner_node,
    researcher_node,
    itinerary_builder_node,
    constraint_checker_node,
    reviewer_node,
    route_after_constraint_check,
)

workflow = StateGraph(TravelState)

# ── Nodes ─────────────────────────────────────────────────────────────────────
workflow.add_node("planner",            planner_node)
workflow.add_node("researcher",         researcher_node)
workflow.add_node("itinerary_builder",  itinerary_builder_node)
workflow.add_node("constraint_checker", constraint_checker_node)
workflow.add_node("reviewer",           reviewer_node)

# ── Edges ─────────────────────────────────────────────────────────────────────
workflow.set_entry_point("planner")

workflow.add_edge("planner",           "researcher")
workflow.add_edge("researcher",        "itinerary_builder")
workflow.add_edge("itinerary_builder", "constraint_checker")

# Conditional: constraint_checker → itinerary_builder (rebuild) OR reviewer (proceed)
workflow.add_conditional_edges(
    "constraint_checker",
    route_after_constraint_check,
    {
        "rebuild": "itinerary_builder",
        "proceed": "reviewer",
    },
)

workflow.add_edge("reviewer", END)

# ── Compile ───────────────────────────────────────────────────────────────────
graph = workflow.compile(
    checkpointer=checkpointer,
    store=store,
)
