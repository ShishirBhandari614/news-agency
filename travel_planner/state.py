from typing import Optional, TypedDict, List


class DayPlan(TypedDict):
    day: int
    title: str
    activities: List[str]
    meals: List[str]
    accommodation: str
    estimated_cost: str


class BudgetBreakdown(TypedDict):
    accommodation: str
    food: str
    transport: str
    activities: str
    misc: str
    total_estimate: str
    within_budget: bool


class ConstraintReport(TypedDict):
    passed: bool
    issues: List[str]
    suggestions: List[str]


class TravelState(TypedDict):
    # ── Raw user input ────────────────────────────────────────────────────────
    raw_input: str

    # ── Parsed trip constraints (planner output) ──────────────────────────────
    destination: Optional[str]
    days: Optional[int]
    budget: Optional[str]          # "low" | "medium" | "high" | or "$1000" etc.
    interests: Optional[List[str]]
    pace: Optional[str]            # "relaxed" | "moderate" | "packed"
    travel_style: Optional[str]    # "solo" | "couple" | "family" | "group"
    food_preferences: Optional[List[str]]
    accommodation_type: Optional[str]  # "budget" | "mid-range" | "luxury"
    must_visit: Optional[List[str]]
    travel_dates: Optional[str]

    # ── Research output ───────────────────────────────────────────────────────
    destination_research: Optional[str]
    top_attractions: Optional[List[str]]
    local_food: Optional[List[str]]
    practical_tips: Optional[str]

    # ── Itinerary builder output ──────────────────────────────────────────────
    daily_plan: Optional[List[DayPlan]]
    budget_breakdown: Optional[BudgetBreakdown]

    # ── Constraint checker output ─────────────────────────────────────────────
    constraint_report: Optional[ConstraintReport]
    rebuild_count: Optional[int]

    # ── Final reviewed output ─────────────────────────────────────────────────
    final_plan: Optional[str]

    # ── Memory & observability ────────────────────────────────────────────────
    memory_context: Optional[str]
    execution_log: Optional[List[str]]

    # ── Control ───────────────────────────────────────────────────────────────
    status: Optional[str]   # "planning"|"researching"|"building"|"checking"|"reviewing"|"done"|"error"
    error: Optional[str]
