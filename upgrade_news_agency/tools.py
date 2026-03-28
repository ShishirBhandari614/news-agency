from langchain_community.tools import DuckDuckGoSearchResults
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore
from tavily import TavilyClient
import os
from dotenv import load_dotenv
load_dotenv() 
# ── Search tool ───────────────────────────────────────────────────────────────
# Tavily is the primary search — indexes news within hours, much fresher than DDG.
# DDG is kept as a silent fallback in case Tavily fails.
_tavily = TavilyClient(api_key=os.getenv('TAVILY_API_KEY'))
_ddg = DuckDuckGoSearchResults(max_results=6, output_format='list')  # fallback

print(_tavily)

def search(query: str, max_results: int = 6) -> list:
    """
    Search using Tavily with DDG fallback.
    Returns list of dicts with 'title', 'snippet', 'link' keys.
    """
    try:
        response = _tavily.search(
            query=query,
            max_results=max_results,
            search_depth="advanced",
            include_answer=False,
        )
        results = []
        for r in response.get("results", []):
            results.append({
                "title":   r.get("title", ""),
                "snippet": r.get("content", ""),
                "link":    r.get("url", ""),
            })
        return results
    except Exception:
        try:
            return _ddg.invoke(query)
        except Exception:
            return []


# Keep ddg as alias so nothing breaks if imported elsewhere
ddg = type('DDGCompat', (), {'invoke': staticmethod(lambda q: search(q))})() 

# ── Short-term memory: thread-level checkpointing ─────────────────────────────
# Saves full graph state at every step for a given thread_id.
# Each Streamlit run gets its own thread_id → full replay / inspection possible.
checkpointer = MemorySaver()

# ── Long-term memory: cross-thread persistent store ───────────────────────────
# Namespaces:
#   ("newsroom", "preferences")  → writing style config
#   ("newsroom", "topics")       → one record per covered topic
#   ("newsroom", "run_history")  → lightweight run log entries
store = InMemoryStore()

_PREF_NS    = ("newsroom", "preferences")
_TOPICS_NS  = ("newsroom", "topics")
_HISTORY_NS = ("newsroom", "run_history")
_ARTICLES_NS  = ("newsroom", "articles")  # full article context per run
_THREADS_NS   = ("newsroom", "threads")   # thread_id → topic name mapping

# Seed default style preferences on first import
if not store.get(_PREF_NS, "style"):
    store.put(_PREF_NS, "style", {
        "tone": "professional and factual",
        "preferred_length": "300-400 words",
        "trusted_source_categories": ["government", "academic", "major news outlets"],
    })


# ── Style preferences ─────────────────────────────────────────────────────────

def get_style_prefs() -> dict:
    item = store.get(_PREF_NS, "style")
    return item.value if item else {}


def save_style_prefs(prefs: dict):
    store.put(_PREF_NS, "style", prefs)


# ── Topic memory ──────────────────────────────────────────────────────────────

def get_covered_topics() -> list:
    items = store.search(_TOPICS_NS)
    return [item.value["topic"] for item in items if "topic" in item.value]


def record_topic(topic: str):
    key = topic.lower().replace(" ", "_")[:60]
    store.put(_TOPICS_NS, key, {"topic": topic})


# ── Run history ───────────────────────────────────────────────────────────────

def get_recent_runs(n: int = 5) -> list:
    items = store.search(_HISTORY_NS)
    runs = sorted(
        [item.value for item in items],
        key=lambda x: x.get("timestamp", ""),
        reverse=True,
    )
    return runs[:n]


def record_run(topic: str, output_format: str, success: bool):
    from datetime import datetime
    ts = datetime.now().isoformat()
    key = ts.replace(":", "-").replace(".", "-")
    store.put(_HISTORY_NS, key, {
        "topic": topic,
        "format": output_format,
        "success": success,
        "timestamp": ts,
    })


# ── Article context memory ───────────────────────────────────────────────────

def save_article_context(topic: str, plan: str, research_notes: str, final: str, output_format: str):
    """Save the full article context so future runs on related topics can reference it."""
    from datetime import datetime
    ts = datetime.now().isoformat()
    key = topic.lower().replace(" ", "_")[:60] + "__" + ts[:10]
    store.put(_ARTICLES_NS, key, {
        "topic": topic,
        "plan": plan or "",
        "research_notes": research_notes or "",
        "final": final or "",
        "output_format": output_format or "article",
        "timestamp": ts,
    })


def get_related_articles(topic: str, n: int = 3) -> list:
    """Return up to n previously saved articles whose topic overlaps with the current one."""
    items = store.search(_ARTICLES_NS)
    topic_words = set(topic.lower().split())
    scored = []
    for item in items:
        stored_topic = item.value.get("topic", "")
        stored_words = set(stored_topic.lower().split())
        overlap = len(topic_words & stored_words)
        if overlap > 0:
            scored.append((overlap, item.value))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [v for _, v in scored[:n]]


def get_last_article() -> dict | None:
    """Return the most recently saved article from the store."""
    items = store.search(_ARTICLES_NS)
    if not items:
        return None
    return max(items, key=lambda x: x.value.get("timestamp", "")).value


def clear_articles():
    """Delete all saved article contexts."""
    items = store.search(_ARTICLES_NS)
    for item in items:
        store.delete(_ARTICLES_NS, item.key)


# ── Thread registry (for chat history sidebar) ───────────────────────────────

def register_thread(thread_id: str, topic: str):
    """Save thread_id → first topic so sidebar can list all past chats."""
    from datetime import datetime
    store.put(_THREADS_NS, thread_id, {
        "thread_id": thread_id,
        "topic": topic,
        "timestamp": datetime.now().isoformat(),
    })


def get_all_threads() -> list:
    """Return all threads sorted newest first."""
    items = store.search(_THREADS_NS)
    threads = [item.value for item in items]
    return sorted(threads, key=lambda x: x.get("timestamp", ""), reverse=True)


def delete_thread(thread_id: str):
    """Remove a thread from the registry."""
    store.delete(_THREADS_NS, thread_id)


# ── Clear helpers ────────────────────────────────────────────────────────────

def clear_topics():
    """Delete all covered topics, article contexts and threads from the long-term store."""
    items = store.search(_TOPICS_NS)
    for item in items:
        store.delete(_TOPICS_NS, item.key)
    clear_articles()
    # clear thread registry too
    for item in store.search(_THREADS_NS):
        store.delete(_THREADS_NS, item.key)


# ── Memory context builder ────────────────────────────────────────────────────

def build_memory_context(topic: str) -> str:
    """Summarise long-term memory into a context string for LLM prompts.
    Includes style prefs, related past articles (plan + research summary), and recent topics.
    """
    prefs   = get_style_prefs()
    covered = get_covered_topics()
    recent  = get_recent_runs(5)
    related_articles = get_related_articles(topic, n=2)

    related_topic_names = [t for t in covered if any(w in topic.lower() for w in t.lower().split())]

    lines = [
        f"Writing tone: {prefs.get('tone', 'professional and factual')}",
        f"Preferred length: {prefs.get('preferred_length', '300-400 words')}",
        f"Trusted sources: {', '.join(prefs.get('trusted_source_categories', []))}",
    ]

    if related_topic_names:
        lines.append(f"Previously covered related topics: {', '.join(related_topic_names[:5])}")

    if recent:
        lines.append(f"Recent newsroom topics: {', '.join(r['topic'] for r in recent)}")

    # Inject summaries of related past articles so agents can build on prior work
    if related_articles:
        lines.append("\n--- CONTEXT FROM PREVIOUS RELATED ARTICLES ---")
        for art in related_articles:
            lines.append(f"Topic: {art.get('topic','?')} ({art.get('output_format','article')})")
            if art.get('plan'):
                lines.append(f"Previous plan: {art['plan'][:300]}")
            if art.get('research_notes'):
                lines.append(f"Previous research summary: {art['research_notes'][:400]}")
            if art.get('final'):
                lines.append(f"Previous article excerpt: {art['final'][:500]}")
            lines.append("")

    return "\n".join(lines)