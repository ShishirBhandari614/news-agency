import json
import logging
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langgraph.store.base import BaseStore

from state import TravelState
from tools import ddg, build_memory_context, record_trip, record_run, get_city_costs, format_cost_context

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("travel_planner.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("travel")

MAX_REBUILDS = 2
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.4)


def _log(state: TravelState, message: str) -> TravelState:
    logger.info(message)
    log = list(state.get("execution_log") or [])
    log.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
    state["execution_log"] = log
    return state

PLANNER_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are a travel planning assistant. Parse the user's travel request and extract structured information.\n"
     "Return ONLY valid JSON with these keys:\n"
     '{{'
     '"destination": "<city or country>", '
     '"days": <integer or null>, '
     '"budget": "<low|medium|high|or specific amount>", '
     '"interests": ["<interest1>", ...], '
     '"pace": "<relaxed|moderate|packed>", '
     '"travel_style": "<solo|couple|family|group>", '
     '"food_preferences": ["<pref1>", ...], '
     '"accommodation_type": "<budget|mid-range|luxury>", '
     '"must_visit": ["<place1>", ...], '
     '"travel_dates": "<dates or null>"'
     '}}\n'
     "If a field is not mentioned, use sensible defaults:\n"
     "- days: 5, budget: medium, pace: moderate, travel_style: solo, accommodation_type: mid-range\n"
     "- interests, food_preferences, must_visit: empty list if not mentioned\n"
     "Memory context (use to fill gaps from user preferences):\n{memory_context}"),
    ("human", "User request: {raw_input}"),
])

RESEARCHER_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are a travel researcher. Given a destination and trip details, write helpful research notes.\n"
     "Return ONLY valid JSON:\n"
     '{{'
     '"destination_research": "<2-3 paragraph overview of the destination>", '
     '"top_attractions": ["<attraction1>", "<attraction2>", ...], '
     '"local_food": ["<dish or restaurant type1>", ...], '
     '"practical_tips": "<visa, currency, transport, best areas to stay, safety tips>"'
     '}}\n'
     "Tailor results to the user's interests: {interests}\n"
     "Travel style: {travel_style} | Pace: {pace}\n"
     "Base your response on the search results provided. Be specific and practical."),
    ("human",
     "Destination: {destination}\n"
     "Days: {days}\n"
     "Must-visit: {must_visit}\n\n"
     "Search Results:\n{search_results}"),
])

ITINERARY_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are an expert itinerary builder. Create a detailed day-by-day travel plan.\n"
     "Return ONLY valid JSON:\n"
     '{{'
     '"daily_plan": ['
     '  {{"day": 1, "title": "<Day theme>", "activities": ["<activity1>", ...], '
     '    "meals": ["Breakfast: ...", "Lunch: ...", "Dinner: ..."], '
     '    "accommodation": "<hotel type or area>", "estimated_cost": "<$XX-XX>"}},'
     '  ...'
     '], '
     '"budget_breakdown": {{'
     '  "accommodation": "<$XX total>", '
     '  "food": "<$XX total>", '
     '  "transport": "<$XX total>", '
     '  "activities": "<$XX total>", '
     '  "misc": "<$XX total>", '
     '  "total_estimate": "<$XX-XX>", '
     '  "within_budget": true|false'
     '}}'
     '}}\n'
     "RULES:\n"
     "- Pace: {pace} — relaxed means 2-3 activities/day, moderate means 3-4, packed means 5+\n"
     "- Budget level: {budget} — low=$30-60/day, medium=$80-150/day, high=$200+/day\n"
     "- Match accommodation to: {accommodation_type}\n"
     "- Include must-visit places: {must_visit}\n"
     "- Food preferences: {food_preferences}\n"
     "- Set within_budget=false if total exceeds the budget level.\n"
     "IMPORTANT — USE REAL PRICE DATA BELOW if available. "
     "These are actual current prices from Numbeo for this city. "
     "Use them to calculate realistic per-day and total costs instead of guessing:\n"
     "{cost_context}\n"
     "Use the research notes and memory context to personalise the plan."),
    ("human",
     "Destination: {destination} | Days: {days} | Travel style: {travel_style}\n"
     "Research notes:\n{destination_research}\n"
     "Top attractions: {top_attractions}\n"
     "Local food: {local_food}\n"
     "Memory context:\n{memory_context}"),
])

CONSTRAINT_CHECKER_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are a travel constraint checker. Review the itinerary against user requirements.\n"
     "Return ONLY valid JSON:\n"
     '{{'
     '"passed": true|false, '
     '"issues": ["<issue1>", ...], '
     '"suggestions": ["<suggestion1>", ...]'
     '}}\n'
     "Check for:\n"
     "1. Budget — does total_estimate fit the budget level ({budget})?\n"
     "2. Pace — does activity density match the requested pace ({pace})?\n"
     "3. Must-visit — are all must-visit places included: {must_visit}?\n"
     "4. Days — does the plan cover exactly {days} days?\n"
     "5. Interests — does the plan reflect these interests: {interests}?\n"
     "passed=false if budget is exceeded OR must-visit places are missing.\n"
     "passed=true for minor issues — just add suggestions."),
    ("human",
     "Budget level: {budget} | Pace: {pace} | Days: {days}\n"
     "Must-visit: {must_visit}\n"
     "Interests: {interests}\n\n"
     "Itinerary:\n{itinerary_summary}\n\n"
     "Budget breakdown:\n{budget_breakdown}"),
])

REVIEWER_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are a travel editor. Polish and format the itinerary into a beautiful, practical final travel plan.\n"
     "Structure the output as follows:\n\n"
     "TRIP SUMMARY\n"
     "Write 2-3 sentences summarising the trip.\n\n"
     "BUDGET ESTIMATE\n"
     "List the budget breakdown clearly.\n\n"
     "DAY-BY-DAY ITINERARY\n"
     "For each day: bold the day title, list activities, meals, and accommodation.\n\n"
     "FOOD & DINING HIGHLIGHTS\n"
     "3-5 must-try foods or restaurants.\n\n"
     "TIPS & NOTES\n"
     "Practical travel tips (visa, transport, safety, best time to visit).\n\n"
     "If there are constraint checker suggestions, incorporate them naturally.\n"
     "Write in a warm, friendly tone. Return the formatted text directly — no JSON."),
    ("human",
     "Destination: {destination} | Days: {days} | Travel style: {travel_style}\n"
     "Budget: {budget} | Pace: {pace}\n\n"
     "Daily plan:\n{daily_plan}\n\n"
     "Budget breakdown:\n{budget_breakdown}\n\n"
     "Practical tips:\n{practical_tips}\n\n"
     "Suggestions from constraint checker:\n{suggestions}\n\n"
     "Memory context:\n{memory_context}"),
])


# ── Nodes ─────────────────────────────────────────────────────────────────────

def planner_node(state: TravelState, config: RunnableConfig, *, store: BaseStore) -> TravelState:
    state["status"] = "planning"
    state = _log(state, f"PLANNER parsing user input: {state['raw_input'][:80]}...")

    memory_context = build_memory_context(state.get("raw_input", ""))
    state["memory_context"] = memory_context

    chain  = PLANNER_PROMPT | llm
    output = chain.invoke({
        "raw_input":      state["raw_input"],
        "memory_context": memory_context,
    })

    try:
        clean     = output.content.replace("```json", "").replace("```", "").strip()
        parsed    = json.loads(clean)
        state["destination"]        = parsed.get("destination", "Unknown")
        state["days"]               = int(parsed.get("days") or 5)
        state["budget"]             = parsed.get("budget", "medium")
        state["interests"]          = parsed.get("interests", [])
        state["pace"]               = parsed.get("pace", "moderate")
        state["travel_style"]       = parsed.get("travel_style", "solo")
        state["food_preferences"]   = parsed.get("food_preferences", [])
        state["accommodation_type"] = parsed.get("accommodation_type", "mid-range")
        state["must_visit"]         = parsed.get("must_visit", [])
        state["travel_dates"]       = parsed.get("travel_dates")
    except Exception as e:
        state["destination"]        = "Unknown destination"
        state["days"]               = 5
        state["budget"]             = "medium"
        state["interests"]          = []
        state["pace"]               = "moderate"
        state["travel_style"]       = "solo"
        state["food_preferences"]   = []
        state["accommodation_type"] = "mid-range"
        state["must_visit"]         = []
        state = _log(state, f"PLANNER parse error (using defaults): {e}")

    state = _log(
        state,
        f"PLANNER done — {state['destination']} | {state['days']} days | "
        f"budget={state['budget']} | pace={state['pace']}"
    )
    return state


def researcher_node(state: TravelState) -> TravelState:
    state["status"] = "researching"
    state = _log(state, f"RESEARCHER searching for {state['destination']}...")

    destination = state.get("destination", "")
    interests   = ", ".join(state.get("interests") or [])
    queries = [
        f"{destination} top attractions things to do",
        f"{destination} local food best restaurants",
        f"{destination} travel tips budget accommodation transport",
    ]
    if state.get("must_visit"):
        queries.append(f"{destination} {' '.join(state['must_visit'][:3])}")

    all_results = []
    for q in queries:
        for r in ddg.invoke(q):
            all_results.append(
                f"[{r.get('title','?')}] {r.get('snippet','')} ({r.get('link','')})"
            )

    search_text = "\n".join(all_results) if all_results else "No search results available."

    state = _log(state, f"RESEARCHER fetching real prices from Numbeo for {destination}...")
    costs     = get_city_costs(destination)
    cost_text = format_cost_context(costs)
    if costs:
        state = _log(state, f"RESEARCHER got real prices: meal={costs.get('meal_cheap','?')}, transport={costs.get('local_transport','?')}")
    else:
        state = _log(state, "RESEARCHER could not fetch Numbeo prices — will use LLM estimates")

    state["cost_context"] = cost_text

    chain  = RESEARCHER_PROMPT | llm
    output = chain.invoke({
        "destination":    destination,
        "days":           state.get("days", 5),
        "interests":      interests or "general sightseeing",
        "travel_style":   state.get("travel_style", "solo"),
        "pace":           state.get("pace", "moderate"),
        "must_visit":     ", ".join(state.get("must_visit") or []) or "none specified",
        "search_results": search_text,
    })

    try:
        clean   = output.content.replace("```json", "").replace("```", "").strip()
        data    = json.loads(clean)
        state["destination_research"] = data.get("destination_research", "")
        state["top_attractions"]      = data.get("top_attractions", [])
        state["local_food"]           = data.get("local_food", [])
        state["practical_tips"]       = data.get("practical_tips", "")
    except Exception:
        state["destination_research"] = output.content
        state["top_attractions"]      = []
        state["local_food"]           = []
        state["practical_tips"]       = ""

    state = _log(
        state,
        f"RESEARCHER done — {len(state.get('top_attractions') or [])} attractions found"
    )
    return state


def itinerary_builder_node(state: TravelState) -> TravelState:
    state["status"] = "building"
    rebuild = state.get("rebuild_count") or 0
    state = _log(state, f"ITINERARY BUILDER creating plan (attempt {rebuild + 1})...")

    chain  = ITINERARY_PROMPT | llm
    output = chain.invoke({
        "destination":          state.get("destination", ""),
        "days":                 state.get("days", 5),
        "travel_style":         state.get("travel_style", "solo"),
        "budget":               state.get("budget", "medium"),
        "pace":                 state.get("pace", "moderate"),
        "accommodation_type":   state.get("accommodation_type", "mid-range"),
        "must_visit":           ", ".join(state.get("must_visit") or []) or "none",
        "food_preferences":     ", ".join(state.get("food_preferences") or []) or "no preference",
        "destination_research": state.get("destination_research", ""),
        "top_attractions":      ", ".join(state.get("top_attractions") or []),
        "local_food":           ", ".join(state.get("local_food") or []),
        "memory_context":       state.get("memory_context", ""),
        "cost_context":         state.get("cost_context", "No real price data available."),
    })

    try:
        clean   = output.content.replace("```json", "").replace("```", "").strip()
        data    = json.loads(clean)
        state["daily_plan"]       = data.get("daily_plan", [])
        state["budget_breakdown"] = data.get("budget_breakdown", {})
    except Exception:
        state["daily_plan"]       = []
        state["budget_breakdown"] = {}

    state = _log(
        state,
        f"ITINERARY BUILDER done — {len(state.get('daily_plan') or [])} days planned"
    )
    return state


def constraint_checker_node(state: TravelState) -> TravelState:
    state["status"] = "checking"
    rebuild_count = (state.get("rebuild_count") or 0) + 1
    state["rebuild_count"] = rebuild_count
    state = _log(state, f"CONSTRAINT CHECKER running (attempt {rebuild_count}/{MAX_REBUILDS})...")

    # Summarise itinerary for the prompt
    daily_plan = state.get("daily_plan") or []
    itinerary_summary = "\n".join(
        f"Day {d.get('day')}: {d.get('title')} — {', '.join(d.get('activities', [])[:3])}"
        for d in daily_plan
    ) or "No itinerary built."

    budget_breakdown = state.get("budget_breakdown") or {}
    budget_text = "\n".join(
        f"{k}: {v}" for k, v in budget_breakdown.items()
    )

    chain  = CONSTRAINT_CHECKER_PROMPT | llm
    output = chain.invoke({
        "budget":            state.get("budget", "medium"),
        "pace":              state.get("pace", "moderate"),
        "days":              state.get("days", 5),
        "must_visit":        ", ".join(state.get("must_visit") or []) or "none",
        "interests":         ", ".join(state.get("interests") or []) or "general",
        "itinerary_summary": itinerary_summary,
        "budget_breakdown":  budget_text,
    })

    try:
        clean  = output.content.replace("```json", "").replace("```", "").strip()
        report = json.loads(clean)
    except Exception:
        report = {"passed": True, "issues": [], "suggestions": []}

    state["constraint_report"] = report
    verdict = "PASSED ✓" if report.get("passed") else "FAILED ✗"
    state = _log(
        state,
        f"CONSTRAINT CHECKER {verdict} | Issues: {len(report.get('issues', []))} | "
        f"Rebuild count: {rebuild_count}"
    )
    return state


def reviewer_node(state: TravelState, config: RunnableConfig, *, store: BaseStore) -> TravelState:
    state["status"] = "reviewing"
    state = _log(state, "REVIEWER polishing final travel plan...")

    report      = state.get("constraint_report") or {}
    suggestions = "\n".join(f"- {s}" for s in report.get("suggestions", [])) or "None"

    daily_plan = state.get("daily_plan") or []
    daily_text = ""
    for d in daily_plan:
        daily_text += (
            f"\nDay {d.get('day')}: {d.get('title')}\n"
            f"  Activities: {', '.join(d.get('activities', []))}\n"
            f"  Meals: {', '.join(d.get('meals', []))}\n"
            f"  Stay: {d.get('accommodation', '')}\n"
            f"  Est. cost: {d.get('estimated_cost', '')}\n"
        )

    budget_breakdown = state.get("budget_breakdown") or {}
    budget_text = "\n".join(f"  {k}: {v}" for k, v in budget_breakdown.items())

    chain  = REVIEWER_PROMPT | llm
    output = chain.invoke({
        "destination":     state.get("destination", ""),
        "days":            state.get("days", 5),
        "travel_style":    state.get("travel_style", "solo"),
        "budget":          state.get("budget", "medium"),
        "pace":            state.get("pace", "moderate"),
        "daily_plan":      daily_text or "No daily plan available.",
        "budget_breakdown": budget_text or "No budget breakdown.",
        "practical_tips":  state.get("practical_tips", ""),
        "suggestions":     suggestions,
        "memory_context":  state.get("memory_context", ""),
    })

    state["final_plan"] = output.content

    record_trip(
        destination=state.get("destination", ""),
        days=state.get("days", 5),
        budget=state.get("budget", "medium"),
        final_plan=output.content,
    )
    record_run(destination=state.get("destination", ""), success=True)

    state = _log(state, "REVIEWER done. Trip plan complete ✓")
    state["status"] = "done"
    return state

def route_after_constraint_check(state: TravelState) -> str:
    report        = state.get("constraint_report") or {}
    passed        = report.get("passed", True)
    rebuild_count = state.get("rebuild_count") or 0

    if not passed and rebuild_count < MAX_REBUILDS:
        logger.info(f"ROUTER → rebuild itinerary (attempt {rebuild_count}/{MAX_REBUILDS})")
        return "rebuild"
    else:
        logger.info("ROUTER → proceed to reviewer")
        return "proceed"