import uuid
import streamlit as st
from dotenv import load_dotenv

from state import NewsState
from graph import graph
from tools import (
    get_style_prefs, save_style_prefs,
    get_covered_topics, get_recent_runs, clear_topics,
    register_thread, get_all_threads, delete_thread,
)

load_dotenv()

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Newsroom",
    page_icon="🗞️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Source+Serif+4:ital,wght@0,300;0,400;1,300&display=swap');

html, body, [class*="css"] { font-family: 'Source Serif 4', serif; }
h1, h2, h3 { font-family: 'Playfair Display', serif !important; }

.masthead {
    text-align: center;
    border-top: 4px solid #1a1a1a;
    border-bottom: 2px solid #1a1a1a;
    padding: 12px 0 8px;
    margin-bottom: 24px;
}
.masthead h1 { font-size: 3rem; letter-spacing: -1px; color: #1a1a1a; margin: 0; }
.masthead .tagline {
    font-size: 0.8rem; letter-spacing: 3px;
    text-transform: uppercase; color: #666; margin-top: 4px;
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
.step-badge.active { background: #1a1a1a; color: #fff; border-color: #1a1a1a; }

.article-card {
    background: #fffef8; border: 1px solid #e0ddd0;
    border-radius: 4px; padding: 28px 32px;
    font-size: 1.05rem; line-height: 1.85;
    white-space: pre-wrap; font-family: 'Source Serif 4', Georgia, serif;
    color: #1a1a1a;
}

.verdict-pass {
    background: #e8f5e9; border-left: 4px solid #2e7d32;
    padding: 10px 16px; border-radius: 0 4px 4px 0;
    color: #1b5e20; font-weight: 600;
}
.verdict-fail {
    background: #fce4ec; border-left: 4px solid #c62828;
    padding: 10px 16px; border-radius: 0 4px 4px 0;
    color: #b71c1c; font-weight: 600;
}

.claim-supported { color: #2e7d32; }
.claim-weak      { color: #e65100; }
.claim-unsupported { color: #c62828; }

.log-box {
    background: #1a1a1a; color: #a8d8a8;
    font-family: 'Courier New', monospace; font-size: 0.78rem;
    padding: 14px; border-radius: 4px;
    max-height: 220px; overflow-y: auto; white-space: pre-wrap;
}

.memory-chip {
    display: inline-block; background: #f5f0e8;
    border: 1px solid #d4c9b0; border-radius: 12px;
    padding: 3px 10px; font-size: 0.78rem; color: #5c4a2a; margin: 2px;
}

/* Chat history item styling */
.chat-item-active {
    background: #1a1a1a !important;
    color: #fff !important;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 0.85rem;
}
.chat-item {
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 0.85rem;
}
</style>
""", unsafe_allow_html=True)

# ── Masthead ──────────────────────────────────────────────────────────────────
st.markdown("""
<div class="masthead">
  <h1>🗞 THE AI NEWSROOM</h1>
  <div class="tagline">Planner · Researcher · Writer · Fact‑Checker · Editor · Publisher</div>
</div>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
# messages: list of dicts for the current chat window
if "messages" not in st.session_state:
    st.session_state.messages = []

# thread_id: identifies the current chat session for the checkpointer
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

# all_threads_cache: local dict {thread_id: messages} so switching tabs is instant
if "threads_cache" not in st.session_state:
    st.session_state.threads_cache = {}


# ── Helper: switch to a thread ────────────────────────────────────────────────
def switch_thread(thread_id: str):
    """Save current chat to cache, load the selected thread."""
    # Save current messages into cache before switching
    st.session_state.threads_cache[st.session_state.thread_id] = st.session_state.messages

    # Switch thread
    st.session_state.thread_id = thread_id

    # Load messages from cache if available, else start empty
    st.session_state.messages = st.session_state.threads_cache.get(thread_id, [])


def new_chat():
    """Save current thread to cache and open a blank new thread."""
    st.session_state.threads_cache[st.session_state.thread_id] = st.session_state.messages
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.messages = []


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:

    # ── New Chat button ───────────────────────────────────────────────────────
    if st.button("✏️  New Chat", use_container_width=True):
        new_chat()
        st.rerun()

    st.divider()

    # ── Chat history list (like ChatGPT) ──────────────────────────────────────
    st.caption("**Chats**")
    threads = get_all_threads()

    if threads:
        for t in threads:
            tid   = t["thread_id"]
            topic = t.get("topic", "Untitled")[:35]
            is_active = tid == st.session_state.thread_id

            col_btn, col_del = st.columns([5, 1])
            with col_btn:
                label = f"{'▶ ' if is_active else '📰 '}{topic}"
                if st.button(label, key=f"thread_{tid}", use_container_width=True):
                    switch_thread(tid)
                    st.rerun()
            with col_del:
                if st.button("🗑", key=f"del_{tid}"):
                    delete_thread(tid)
                    # If deleting active thread, open new chat
                    if tid == st.session_state.thread_id:
                        new_chat()
                    if tid in st.session_state.threads_cache:
                        del st.session_state.threads_cache[tid]
                    st.rerun()
    else:
        st.caption("_No chats yet_")

    st.divider()

    # ── Style preferences ─────────────────────────────────────────────────────
    prefs     = get_style_prefs()
    has_prefs = bool(prefs.get("tone"))

    if has_prefs:
        with st.expander("⚙️ Preferences", expanded=False):
            st.markdown(
                f"""<div style='background:#f5f0e8;border:1px solid #d4c9b0;border-radius:6px;
                padding:10px 14px;font-size:0.85rem;color:#3a2e1a;'>
                <b>Tone:</b> {prefs.get('tone','—')}<br>
                <b>Length:</b> {prefs.get('preferred_length','—')}
                </div>""",
                unsafe_allow_html=True,
            )
            st.markdown("")
            tone   = st.text_input("Tone",             value=prefs.get("tone", "professional and factual"), key="pref_tone")
            length = st.text_input("Preferred length", value=prefs.get("preferred_length", "300-400 words"), key="pref_length")
            if st.button("✏️ Update Preference"):
                save_style_prefs({**prefs, "tone": tone, "preferred_length": length})
                st.success("Updated ✓")
                st.rerun()
    else:
        st.caption("**Style preferences**")
        tone   = st.text_input("Tone",             value="professional and factual", key="pref_tone")
        length = st.text_input("Preferred length", value="300-400 words",            key="pref_length")
        if st.button("💾 Save preferences"):
            save_style_prefs({**prefs, "tone": tone, "preferred_length": length})
            st.success("Saved ✓")
            st.rerun()

    st.divider()

    # ── Previously covered topics ─────────────────────────────────────────────
    st.caption("**Previously covered topics**")
    covered = get_covered_topics()
    if covered:
        for t in covered[-10:]:
            st.markdown(f'<span class="memory-chip">{t}</span>', unsafe_allow_html=True)
    else:
        st.caption("_None yet_")

    st.divider()

    # ── Clear everything ──────────────────────────────────────────────────────
    if st.button("🗑 Clear all chats & memory", use_container_width=True):
        st.session_state.messages      = []
        st.session_state.threads_cache = {}
        st.session_state.thread_id     = str(uuid.uuid4())
        clear_topics()   # clears topics + articles + threads from store
        st.rerun()


# ── Pipeline status bar ───────────────────────────────────────────────────────
STEPS = ["planner", "researcher", "writer", "fact_checker", "editor", "publisher"]

def render_pipeline(current: str = ""):
    badges = "".join(
        f'<span class="step-badge {"active" if s == current else ""}">{s.replace("_"," ")}</span>'
        for s in STEPS
    )
    st.markdown(f'<div class="pipeline-bar">{badges}</div>', unsafe_allow_html=True)

render_pipeline()


# ── Result renderer ───────────────────────────────────────────────────────────
def render_result(state: dict):
    prefs        = get_style_prefs()
    tone_label   = prefs.get("tone", "—")
    length_label = prefs.get("preferred_length", "—")
    fmt_label    = state.get("output_format", "article")

    st.markdown(
        f'<div style="font-size:0.8rem;color:#888;margin-bottom:8px;font-family:monospace;">'
        f'📰 <b>{fmt_label}</b> &nbsp;·&nbsp; tone: <i>{tone_label}</i> &nbsp;·&nbsp; length: <i>{length_label}</i>'
        f'</div>',
        unsafe_allow_html=True,
    )

    tabs = st.tabs(["📋 Plan", "🔍 Research", "✍️ Draft", "✅ Fact-Check", "✏️ Edited", "🗞 Final", "📜 Log"])

    with tabs[0]:
        st.markdown(f"**Output format:** `{state.get('output_format','—')}`")
        st.markdown(f"**Plan:** {state.get('plan','—')}")
        if state.get("research_queries"):
            st.markdown("**Research queries:**")
            for q in state["research_queries"]:
                st.markdown(f"- {q}")
        if state.get("required_sections"):
            st.markdown("**Required sections:** " + ", ".join(state["required_sections"]))

    with tabs[1]:
        st.markdown(state.get("research_notes") or "_No notes_")
        if state.get("extracted_claims"):
            st.markdown("**Extracted claims:**")
            for c in state["extracted_claims"]:
                st.markdown(f"- {c}")

    with tabs[2]:
        st.markdown(f'<div class="article-card">{state.get("draft","_No draft_")}</div>', unsafe_allow_html=True)

    with tabs[3]:
        report  = state.get("fact_report") or {}
        verdict = report.get("verdict", "—")
        css     = "verdict-pass" if verdict == "pass" else "verdict-fail"
        icon    = "✅" if verdict == "pass" else "❌"
        st.markdown(f'<div class="{css}">{icon} Verdict: {verdict.upper()}</div>', unsafe_allow_html=True)

        revisions = state.get("revision_count") or 0
        if revisions:
            st.caption(f"🔄 Went through {revisions} revision(s)")

        if report.get("issues"):
            st.markdown("**Issues found:**")
            for i in report["issues"]:
                st.markdown(f"- ⚠️ {i}")

        if report.get("claim_checks"):
            st.markdown("**Claim-by-claim analysis:**")
            icons = {"supported": "✅", "weak": "⚠️", "unsupported": "❌"}
            for cc in report["claim_checks"]:
                s     = cc.get("status", "?")
                css_c = {"supported": "claim-supported", "weak": "claim-weak", "unsupported": "claim-unsupported"}.get(s, "")
                st.markdown(
                    f'{icons.get(s,"•")} <span class="{css_c}"><b>{s.upper()}</b></span> — {cc.get("claim","")}<br>'
                    f'<small>Evidence: {cc.get("evidence","—")}</small>',
                    unsafe_allow_html=True,
                )
                st.markdown("---")

    with tabs[4]:
        st.markdown(f'<div class="article-card">{state.get("edited","_Not edited yet_")}</div>', unsafe_allow_html=True)

    with tabs[5]:
        st.markdown(f'<div class="article-card">{state.get("final","_Not published yet_")}</div>', unsafe_allow_html=True)

    with tabs[6]:
        logs = state.get("execution_log") or []
        st.markdown(
            f'<div class="log-box">{"<br>".join(logs) or "No logs."}</div>',
            unsafe_allow_html=True,
        )


# ── Render current chat messages ──────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.markdown(f"**{msg['content']}**")
        else:
            render_result(msg)


# ── Main input ────────────────────────────────────────────────────────────────
if topic := st.chat_input("Enter a news topic…"):

    is_first_message = len(st.session_state.messages) == 0

    st.session_state.messages.append({"role": "user", "content": topic})
    with st.chat_message("user"):
        st.markdown(f"**{topic}**")

    init_state: NewsState = {
        "topic": topic.strip(),
        "plan": None,
        "research_queries": None,
        "required_sections": None,
        "output_format": None,
        "research_notes": None,
        "extracted_claims": None,
        "draft": None,
        "fact_report": None,
        "revision_count": 0,
        "edited": None,
        "final": None,
        "memory_context": None,
        "execution_log": [],
        "status": None,
        "error": None,
    }

    run_config = {"configurable": {"thread_id": st.session_state.thread_id}}

    status_placeholder = st.empty()

    with st.spinner("Running newsroom pipeline…"):
        final_state = None
        for step_output in graph.stream(init_state, config=run_config):
            for node_name, node_state in step_output.items():
                with status_placeholder.container():
                    render_pipeline(node_name)
                    st.caption(f"⏳ Running **{node_name.replace('_', ' ')}**…")
                final_state = node_state

    status_placeholder.empty()
    render_pipeline("publisher")

    with st.chat_message("assistant"):
        render_result(final_state)

    st.session_state.messages.append({"role": "assistant", **final_state})

    # Register thread in store on first message of this thread
    if is_first_message:
        register_thread(st.session_state.thread_id, topic.strip())
        # Also save to cache
        st.session_state.threads_cache[st.session_state.thread_id] = st.session_state.messages

    st.rerun()