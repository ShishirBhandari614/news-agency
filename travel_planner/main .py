import uuid
import streamlit as st
from dotenv import load_dotenv

from state import TravelState
from graph import graph
from tools import (
    get_travel_prefs, save_travel_prefs,
    get_past_destinations, clear_all,
    register_thread, get_all_threads, delete_thread,
)

load_dotenv()

st.set_page_config(
    page_title="AI Travel Planner",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Source+Serif+4:ital,wght@0,300;0,400;1,300&display=swap');

html, body, [class*="css"] { font-family: 'Source Serif 4', serif; }
h1, h2, h3 { font-family: 'Playfair Display', serif !important; }

.masthead {
    text-align: center;
    border-top: 4px solid #1a5276;
    border-bottom: 2px solid #1a5276;
    padding: 12px 0 8px;
    margin-bottom: 24px;
    background: linear-gradient(135deg, #eaf4fb 0%, #fdfefe 100%);
    border-radius: 8px;
}
.masthead h1 { font-size: 2.8rem; letter-spacing: -1px; color: #1a5276; margin: 0; }
.masthead .tagline {
    font-size: 0.8rem; letter-spacing: 3px;
    text-transform: uppercase; color: #5d6d7e; margin-top: 4px;
}

.pipeline-bar {
    display: flex; gap: 6px; justify-content: center;
    margin-bottom: 20px; flex-wrap: wrap;
}
.step-badge {
    padding: 4px 14px; border-radius: 20px;
    font-size: 0.75rem; font-family: monospace;
    letter-spacing: 1px; text-transform: uppercase;
    background: #f0f0f0; color: #888; border: 1px solid #ddd;
}
.step-badge.active { background: #1a5276; color: #fff; border-color: #1a5276; }

.plan-card {
    background: #fdfefe;
    border: 1px solid #d6eaf8;
    border-radius: 8px;
    padding: 28px 32px;
    font-size: 1.05rem;
    line-height: 1.85;
    white-space: pre-wrap;
    font-family: 'Source Serif 4', Georgia, serif;
    color: #1a1a1a;
}

.verdict-pass {
    background: #e8f8f5; border-left: 4px solid #1e8449;
    padding: 10px 16px; border-radius: 0 4px 4px 0;
    color: #145a32; font-weight: 600;
}
.verdict-fail {
    background: #fce4ec; border-left: 4px solid #c62828;
    padding: 10px 16px; border-radius: 0 4px 4px 0;
    color: #b71c1c; font-weight: 600;
}

.log-box {
    background: #1a1a1a; color: #a8d8a8;
    font-family: 'Courier New', monospace; font-size: 0.78rem;
    padding: 14px; border-radius: 4px;
    max-height: 220px; overflow-y: auto; white-space: pre-wrap;
}

.memory-chip {
    display: inline-block; background: #d6eaf8;
    border: 1px solid #aed6f1; border-radius: 12px;
    padding: 3px 10px; font-size: 0.78rem; color: #1a5276; margin: 2px;
}

.example-chip {
    display: inline-block; background: #f0f3f4;
    border: 1px solid #d5d8dc; border-radius: 6px;
    padding: 4px 12px; font-size: 0.82rem; color: #2c3e50; margin: 3px;
    cursor: pointer;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="masthead">
  <h1>✈️ AI TRAVEL PLANNER</h1>
  <div class="tagline">Planner · Researcher · Itinerary Builder · Constraint Checker · Reviewer</div>
</div>
""", unsafe_allow_html=True)

if "messages" not in st.session_state:
    st.session_state.messages = []
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "threads_cache" not in st.session_state:
    st.session_state.threads_cache = {}


def switch_thread(thread_id: str):
    st.session_state.threads_cache[st.session_state.thread_id] = st.session_state.messages
    st.session_state.thread_id = thread_id
    st.session_state.messages  = st.session_state.threads_cache.get(thread_id, [])


def new_chat():
    st.session_state.threads_cache[st.session_state.thread_id] = st.session_state.messages
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.messages  = []


with st.sidebar:

    if st.button("✏️  New Trip", use_container_width=True):
        new_chat()
        st.rerun()

    st.divider()

    st.caption("**Past Trips**")
    threads = get_all_threads()
    if threads:
        for t in threads:
            tid   = t["thread_id"]
            dest  = t.get("destination", "Untitled")[:30]
            is_active = tid == st.session_state.thread_id
            col_btn, col_del = st.columns([5, 1])
            with col_btn:
                label = f"{'▶ ' if is_active else '🌍 '}{dest}"
                if st.button(label, key=f"thread_{tid}", use_container_width=True):
                    switch_thread(tid)
                    st.rerun()
            with col_del:
                if st.button("🗑", key=f"del_{tid}"):
                    delete_thread(tid)
                    if tid == st.session_state.thread_id:
                        new_chat()
                    if tid in st.session_state.threads_cache:
                        del st.session_state.threads_cache[tid]
                    st.rerun()
    else:
        st.caption("_No trips yet_")

    st.divider()

    prefs = get_travel_prefs()
    st.caption("**Your Travel Preferences**")
    with st.expander("⚙️ Edit Preferences", expanded=False):
        pace     = st.selectbox("Pace",          ["relaxed", "moderate", "packed"],
                                index=["relaxed", "moderate", "packed"].index(prefs.get("pace", "moderate")))
        accom    = st.selectbox("Accommodation", ["budget", "mid-range", "luxury"],
                                index=["budget", "mid-range", "luxury"].index(prefs.get("accommodation", "mid-range")))
        cuisines = st.text_input("Preferred cuisines (comma-separated)",
                                 value=", ".join(prefs.get("preferred_cuisines", [])))
        dislikes = st.text_input("Disliked activities (comma-separated)",
                                 value=", ".join(prefs.get("disliked_activities", [])))
        if st.button("💾 Save preferences"):
            save_travel_prefs({
                **prefs,
                "pace":               pace,
                "accommodation":      accom,
                "preferred_cuisines": [c.strip() for c in cuisines.split(",") if c.strip()],
                "disliked_activities": [d.strip() for d in dislikes.split(",") if d.strip()],
            })
            st.success("Saved ✓")
            st.rerun()

    st.divider()

    st.caption("**Previously Planned**")
    past = get_past_destinations()
    if past:
        for p in past[-8:]:
            dest = p.get("destination", "?")
            st.markdown(f'<span class="memory-chip">🌍 {dest}</span>', unsafe_allow_html=True)
    else:
        st.caption("_None yet_")

    st.divider()

    if st.button("🗑 Clear all trips & memory", use_container_width=True):
        st.session_state.messages      = []
        st.session_state.threads_cache = {}
        st.session_state.thread_id     = str(uuid.uuid4())
        clear_all()
        st.rerun()


STEPS = ["planner", "researcher", "itinerary_builder", "constraint_checker", "reviewer"]

def render_pipeline(current: str = ""):
    badges = "".join(
        f'<span class="step-badge {"active" if s == current else ""}">'
        f'{s.replace("_", " ")}</span>'
        for s in STEPS
    )
    st.markdown(f'<div class="pipeline-bar">{badges}</div>', unsafe_allow_html=True)

render_pipeline()


def render_result(state: dict):
    dest   = state.get("destination", "?")
    days   = state.get("days", "?")
    budget = state.get("budget", "?")
    pace   = state.get("pace", "?")
    style  = state.get("travel_style", "?")

    st.markdown(
        f'<div style="font-size:0.8rem;color:#888;margin-bottom:8px;font-family:monospace;">'
        f'🌍 <b>{dest}</b> &nbsp;·&nbsp; {days} days &nbsp;·&nbsp; '
        f'budget: <i>{budget}</i> &nbsp;·&nbsp; pace: <i>{pace}</i> &nbsp;·&nbsp; {style}'
        f'</div>',
        unsafe_allow_html=True,
    )

    tabs = st.tabs([
        "🗺 Plan", "🔍 Research", "📅 Itinerary",
        "✅ Constraints", "🗞 Final Plan", "📜 Log"
    ])

    with tabs[0]:
        st.markdown(f"**Destination:** {dest}")
        st.markdown(f"**Days:** {days} | **Budget:** {budget} | **Pace:** {pace} | **Style:** {style}")
        if state.get("interests"):
            st.markdown(f"**Interests:** {', '.join(state['interests'])}")
        if state.get("must_visit"):
            st.markdown(f"**Must-visit:** {', '.join(state['must_visit'])}")
        if state.get("food_preferences"):
            st.markdown(f"**Food preferences:** {', '.join(state['food_preferences'])}")
        if state.get("accommodation_type"):
            st.markdown(f"**Accommodation:** {state['accommodation_type']}")

    with tabs[1]:
        st.markdown(state.get("destination_research") or "_No research available_")
        if state.get("top_attractions"):
            st.markdown("**Top Attractions:**")
            for a in state["top_attractions"]:
                st.markdown(f"- {a}")
        if state.get("local_food"):
            st.markdown("**Local Food:**")
            for f in state["local_food"]:
                st.markdown(f"- {f}")
        if state.get("practical_tips"):
            st.markdown("**Practical Tips:**")
            st.markdown(state["practical_tips"])
        if state.get("cost_context") and "No real price" not in state["cost_context"]:
            st.markdown("---")
            st.markdown("**💰 Real Price Data (Numbeo)**")
            st.code(state["cost_context"], language=None)

    with tabs[2]:
        daily_plan = state.get("daily_plan") or []
        if daily_plan:
            for day in daily_plan:
                with st.expander(f"Day {day.get('day')}: {day.get('title', '')}"):
                    st.markdown("**Activities:**")
                    for act in day.get("activities", []):
                        st.markdown(f"- {act}")
                    st.markdown("**Meals:**")
                    for meal in day.get("meals", []):
                        st.markdown(f"- {meal}")
                    st.markdown(f"**Stay:** {day.get('accommodation', '—')}")
                    st.markdown(f"**Est. cost:** {day.get('estimated_cost', '—')}")
        else:
            st.markdown("_No itinerary built_")

        bd = state.get("budget_breakdown") or {}
        if bd:
            st.markdown("---\n**Budget Breakdown:**")
            for k, v in bd.items():
                if k != "within_budget":
                    st.markdown(f"- **{k.replace('_',' ').title()}:** {v}")
            within = bd.get("within_budget", True)
            if within:
                st.success("✅ Within budget")
            else:
                st.warning("⚠️ May exceed budget")

    with tabs[3]:
        report  = state.get("constraint_report") or {}
        passed  = report.get("passed", True)
        css     = "verdict-pass" if passed else "verdict-fail"
        icon    = "✅" if passed else "❌"
        st.markdown(
            f'<div class="{css}">{icon} Constraints: {"PASSED" if passed else "FAILED"}</div>',
            unsafe_allow_html=True,
        )
        rebuilds = state.get("rebuild_count") or 0
        if rebuilds > 1:
            st.caption(f"🔄 Itinerary was rebuilt {rebuilds - 1} time(s)")
        if report.get("issues"):
            st.markdown("**Issues found:**")
            for i in report["issues"]:
                st.markdown(f"- ⚠️ {i}")
        if report.get("suggestions"):
            st.markdown("**Suggestions:**")
            for s in report["suggestions"]:
                st.markdown(f"- 💡 {s}")

    with tabs[4]:
        st.markdown(
            f'<div class="plan-card">{state.get("final_plan", "_Not ready yet_")}</div>',
            unsafe_allow_html=True,
        )

    with tabs[5]:
        logs = state.get("execution_log") or []
        st.markdown(
            f'<div class="log-box">{"<br>".join(logs) or "No logs."}</div>',
            unsafe_allow_html=True,
        )


# ── Example prompts ───────────────────────────────────────────────────────────
if not st.session_state.messages:
    st.markdown("**Try one of these:**")
    examples = [
        "Plan a 5-day trip to Japan on a medium budget",
        "I want a relaxed 3-day trip to Pokhara with nature and cafés",
        "Plan a family-friendly 7-day itinerary for Bangkok",
        "Budget solo trip to Vietnam for 10 days",
        "Romantic couple trip to Paris for 4 days, luxury budget",
    ]
    cols = st.columns(3)
    for i, ex in enumerate(examples):
        with cols[i % 3]:
            if st.button(ex, key=f"ex_{i}", use_container_width=True):
                st.session_state["prefill_input"] = ex
                st.rerun()


# ── Render current chat messages ──────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.markdown(f"**{msg['content']}**")
        else:
            render_result(msg)


prefill = st.session_state.pop("prefill_input", None)
user_input = st.chat_input("Describe your trip… e.g. 5 days in Tokyo, medium budget, love street food")

topic = prefill or user_input

if topic:
    is_first_message = len(st.session_state.messages) == 0

    st.session_state.messages.append({"role": "user", "content": topic})
    with st.chat_message("user"):
        st.markdown(f"**{topic}**")

    init_state: TravelState = {
        "raw_input":            topic.strip(),
        "destination":          None,
        "days":                 None,
        "budget":               None,
        "interests":            None,
        "pace":                 None,
        "travel_style":         None,
        "food_preferences":     None,
        "accommodation_type":   None,
        "must_visit":           None,
        "travel_dates":         None,
        "destination_research": None,
        "top_attractions":      None,
        "local_food":           None,
        "practical_tips":       None,
        "cost_context":         None,
        "daily_plan":           None,
        "budget_breakdown":     None,
        "constraint_report":    None,
        "rebuild_count":        0,
        "final_plan":           None,
        "memory_context":       None,
        "execution_log":        [],
        "status":               None,
        "error":                None,
    }

    run_config        = {"configurable": {"thread_id": st.session_state.thread_id}}
    status_placeholder = st.empty()

    with st.spinner("Planning your trip…"):
        final_state = None
        for step_output in graph.stream(init_state, config=run_config):
            for node_name, node_state in step_output.items():
                with status_placeholder.container():
                    render_pipeline(node_name)
                    st.caption(f"⏳ Running **{node_name.replace('_', ' ')}**…")
                final_state = node_state

    status_placeholder.empty()
    render_pipeline("reviewer")

    with st.chat_message("assistant"):
        render_result(final_state)

    st.session_state.messages.append({"role": "assistant", **final_state})

    if is_first_message:
        register_thread(st.session_state.thread_id, final_state.get("destination", topic[:30]))
        st.session_state.threads_cache[st.session_state.thread_id] = st.session_state.messages

    st.rerun()