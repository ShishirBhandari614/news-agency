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

    raw_input: str

    destination: Optional[str]
    days: Optional[int]
    budget: Optional[str]         
    interests: Optional[List[str]]
    pace: Optional[str]            
    travel_style: Optional[str]   
    food_preferences: Optional[List[str]]
    accommodation_type: Optional[str] 
    must_visit: Optional[List[str]]
    travel_dates: Optional[str]

    destination_research: Optional[str]
    top_attractions: Optional[List[str]]
    local_food: Optional[List[str]]
    practical_tips: Optional[str]
    cost_context: Optional[str]     

    daily_plan: Optional[List[DayPlan]]
    budget_breakdown: Optional[BudgetBreakdown]

    constraint_report: Optional[ConstraintReport]
    rebuild_count: Optional[int]

    final_plan: Optional[str]

    memory_context: Optional[str]
    execution_log: Optional[List[str]]

    status: Optional[str]   
    error: Optional[str]