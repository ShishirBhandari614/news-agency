from langchain_community.tools import DuckDuckGoSearchResults
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore
from tavily import TavilyClient
import os
import re
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

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


ddg = type("DDGCompat", (), {"invoke": staticmethod(lambda q: search(q))})()

_NUMBEO_ITEMS = {
    "meal_inexpensive":      1,   
    "meal_midrange":         2,   
    "coffee":                114, 
    "water":                 15,  
    "local_transport":       20,  
    "monthly_pass":          18, 
    "hotel_1bed_city":       27,  
}

def get_city_costs(destination: str) -> dict:
    """
    Fetch real cost-of-living prices for a city from Numbeo's public pages.
    Returns a dict with meal, coffee, transport, and hotel cost estimates.
    Falls back to LLM-friendly empty dict on any failure so the pipeline never breaks.

    Works by scraping Numbeo's public /cost-of-living/in/<City> page —
    no API key required.
    """
    city_slug = destination.strip().replace(" ", "-").title()
    url = f"https://www.numbeo.com/cost-of-living/in/{city_slug}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
    except Exception:
        return {}

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", {"class": "data_wide_table"})
    if not table:
        return {}

    prices: dict[str, str] = {}
    currency_symbol = ""

    for row in table.find_all("tr"):
        cols = row.find_all("td")
        if len(cols) < 2:
            continue
        name  = cols[0].get_text(strip=True)
        price_cell = cols[1].get_text(strip=True)

        match = re.search(r"([$€£¥₹₩฿₫]?)\s*([\d,]+\.?\d*)", price_cell)
        if match:
            if not currency_symbol and match.group(1):
                currency_symbol = match.group(1)
            numeric = match.group(2).replace(",", "")
            prices[name.lower()] = f"{match.group(1)}{numeric}"

    if not prices:
        return {}

    # Map to our travel budget categories
    def find(keywords: list[str]) -> str:
        for key in keywords:
            for name, val in prices.items():
                if key in name:
                    return val
        return ""

    meal_cheap    = find(["inexpensive restaurant", "cheap meal", "fast food"])
    meal_midrange = find(["mid-range restaurant", "3-course", "midrange"])
    coffee        = find(["cappuccino", "coffee"])
    transport     = find(["one-way ticket", "local transport", "transit"])
    hotel_proxy   = find(["1 bedroom", "one bedroom", "apartment in city"])

    result = {
        "source":          "Numbeo (live data)",
        "city":            destination,
        "currency_symbol": currency_symbol or "$",
        "meal_cheap":      meal_cheap      or "N/A",
        "meal_midrange":   meal_midrange   or "N/A",
        "coffee":          coffee          or "N/A",
        "local_transport": transport       or "N/A",
        "hotel_proxy":     hotel_proxy     or "N/A",
        "url":             url,
    }

    return result


def format_cost_context(costs: dict) -> str:
    """
    Turn the get_city_costs() result into a prompt-friendly string
    for the Itinerary Builder to use when estimating the budget.
    """
    if not costs or costs.get("meal_cheap") == "N/A":
        return "No real price data available — use general knowledge for estimates."

    sym = costs.get("currency_symbol", "$")
    lines = [
        f"=== REAL PRICE DATA FOR {costs.get('city','').upper()} (Source: Numbeo) ===",
        f"Cheap meal (restaurant):       {costs.get('meal_cheap', 'N/A')}",
        f"Mid-range meal (2 people):     {costs.get('meal_midrange', 'N/A')}",
        f"Coffee / cappuccino:           {costs.get('coffee', 'N/A')}",
        f"Local transport (one-way):     {costs.get('local_transport', 'N/A')}",
        f"Apartment/hotel cost proxy:    {costs.get('hotel_proxy', 'N/A')}",
        f"Use these real prices to calculate accurate daily costs.",
        f"Data URL: {costs.get('url', '')}",
    ]
    return "\n".join(lines)


checkpointer = MemorySaver()
store        = InMemoryStore()

_PREF_NS     = ("travel", "preferences")
_HISTORY_NS  = ("travel", "history")
_THREADS_NS  = ("travel", "threads")
_TRIPS_NS    = ("travel", "trips")

if not store.get(_PREF_NS, "travel_style"):
    store.put(_PREF_NS, "travel_style", {
        "pace":               "moderate",
        "accommodation":      "mid-range",
        "food_preferences":   [],
        "disliked_activities": [],
        "preferred_cuisines": [],
    })

def get_travel_prefs() -> dict:
    item = store.get(_PREF_NS, "travel_style")
    return item.value if item else {}


def save_travel_prefs(prefs: dict):
    store.put(_PREF_NS, "travel_style", prefs)


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


def record_run(destination: str, success: bool):
    from datetime import datetime
    ts  = datetime.now().isoformat()
    key = ts.replace(":", "-").replace(".", "-")
    store.put(_HISTORY_NS, key, {
        "destination": destination,
        "success":     success,
        "timestamp":   ts,
    })


def clear_all():
    for ns in [_TRIPS_NS, _HISTORY_NS, _THREADS_NS]:
        for item in store.search(ns):
            store.delete(ns, item.key)


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