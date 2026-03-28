from langchain_community.tools import DuckDuckGoSearchResults
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore
from tavily import TavilyClient
import os
from dotenv import load_dotenv

load_dotenv()

# ── Search ────────────────────────────────────────────────────────────────────
_tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
_ddg = DuckDuckGoSearchResults(max_results=6, output_format="list")


def search(query: str, max_results: int = 6) -> list:
    """Search using Tavily with DuckDuckGo fallback."""
    try:
        response = _tavily.search(
            query=query,
            max_results=max_results,
            search_depth="advanced",
            include_answer=False,
        )
        return [
            {
                "title":   r.get("title", ""),
                "snippet": r.get("content", ""),
                "link":    r.get("url", ""),
            }
            for r in response.get("results", [])
        ]
    except Exception:
        try:
            return _ddg.invoke(query)
        except Exception:
            return []


# Compatibility alias
ddg = type("DDGCompat", (), {"invoke": staticmethod(lambda q: search(q))})()

# ── Memory ────────────────────────────────────────────────────────────────────
checkpointer = MemorySaver()
store        = InMemoryStore()

_PREF_NS     = ("travel", "preferences")
_HISTORY_NS  = ("travel", "history")
_THREADS_NS  = ("travel", "threads")
_TRIPS_NS    = ("travel", "trips")

# Seed default travel preferences
if not store.get(_PREF_NS, "travel_style"):
    store.put(_PREF_NS, "travel_style", {
        "pace":               "moderate",
        "accommodation":      "mid-range",
        "food_preferences":   [],
        "disliked_activities": [],
        "preferred_cuisines": [],
    })


# ── Travel preference helpers ─────────────────────────────────────────────────

def get_travel_prefs() -> dict:
    item = store.get(_PREF_NS, "travel_style")
    return item.value if item else {}


def save_travel_prefs(prefs: dict):
    store.put(_PREF_NS, "travel_style", prefs)


# ── Trip history ──────────────────────────────────────────────────────────────

def get_past_destinations() -> list:
    items = store.search(_TRIPS_NS)
    return [item.value for item in items]


def record_trip(destination: str, days: int, budget: str, final_plan: str):
    from datetime import datetime
    ts  = datetime.now().isoformat()
    key = destination.lower().replace(" ", "_")[:50] + "__" + ts[:10]
    store.put(_TRIPS_NS, key, {
        "destination": destination,
        "days":        days,
        "budget":      budget,
        "final_plan":  final_plan[:800],
        "timestamp":   ts,
    })


def get_recent_trips(n: int = 3) -> list:
    items = store.search(_TRIPS_NS)
    trips = sorted(
        [item.value for item in items],
        key=lambda x: x.get("timestamp", ""),
        reverse=True,
    )
    return trips[:n]


# ── Thread registry ───────────────────────────────────────────────────────────

def register_thread(thread_id: str, destination: str):
    from datetime import datetime
    store.put(_THREADS_NS, thread_id, {
        "thread_id":   thread_id,
        "destination": destination,
        "timestamp":   datetime.now().isoformat(),
    })


def get_all_threads() -> list:
    items = store.search(_THREADS_NS)
    return sorted(
        [item.value for item in items],
        key=lambda x: x.get("timestamp", ""),
        reverse=True,
    )


def delete_thread(thread_id: str):
    store.delete(_THREADS_NS, thread_id)


# ── Run history ───────────────────────────────────────────────────────────────

def record_run(destination: str, success: bool):
    from datetime import datetime
    ts  = datetime.now().isoformat()
    key = ts.replace(":", "-").replace(".", "-")
    store.put(_HISTORY_NS, key, {
        "destination": destination,
        "success":     success,
        "timestamp":   ts,
    })


# ── Clear ─────────────────────────────────────────────────────────────────────

def clear_all():
    for ns in [_TRIPS_NS, _HISTORY_NS, _THREADS_NS]:
        for item in store.search(ns):
            store.delete(ns, item.key)


# ── Memory context builder ────────────────────────────────────────────────────

def build_memory_context(destination: str) -> str:
    prefs        = get_travel_prefs()
    recent_trips = get_recent_trips(3)
    past         = get_past_destinations()
    past_names   = [t.get("destination", "") for t in past]

    lines = [
        f"Preferred pace: {prefs.get('pace', 'moderate')}",
        f"Preferred accommodation: {prefs.get('accommodation', 'mid-range')}",
    ]

    if prefs.get("food_preferences"):
        lines.append(f"Food preferences: {', '.join(prefs['food_preferences'])}")

    if prefs.get("disliked_activities"):
        lines.append(f"Disliked activities: {', '.join(prefs['disliked_activities'])}")

    if prefs.get("preferred_cuisines"):
        lines.append(f"Preferred cuisines: {', '.join(prefs['preferred_cuisines'])}")

    if past_names:
        lines.append(f"Past destinations planned: {', '.join(past_names[-5:])}")

    if recent_trips:
        lines.append("\n--- RECENT TRIP CONTEXT ---")
        for t in recent_trips:
            lines.append(
                f"Destination: {t.get('destination','?')} | "
                f"Days: {t.get('days','?')} | Budget: {t.get('budget','?')}"
            )
            if t.get("final_plan"):
                lines.append(f"Previous plan excerpt: {t['final_plan'][:400]}")
            lines.append("")

    return "\n".join(lines)
