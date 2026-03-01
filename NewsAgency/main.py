import json
import streamlit as st
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END
from state import NewsState

load_dotenv()


llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.4)

WRITER_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are a professional news writer. "
     "Write a factual, well-structured news article of 300-400 words on the given topic. "
     "Include a headline, a lead paragraph, body paragraphs, and a concluding paragraph. "
     "Return ONLY the article text - no extra commentary."),
    ("human", "Topic: {topic}"),
])

FACT_CHECKER_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are a meticulous fact-checker. "
     "Review the article below and cross-check key claims using the web search results provided. "
     "Return ONLY valid JSON in this exact shape:\n"
     '{{"verdict": "pass" | "fail", "issues": ["<issue1>", ...], "revised_draft": "<full corrected article or empty string if pass>"}}\n'
     "Set verdict to pass when all major claims appear accurate. "
     "Set verdict to fail when you find clear factual errors; list them in issues and supply a corrected article in revised_draft."),
    ("human",
     "Article:\n{draft}\n\n"
     "Web Search Results (use to verify):\n{search_results}"),
])

EDITOR_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are a senior newspaper editor. "
     "Improve the article clarity, flow, tone, and grammar without changing any facts. "
     "Keep the structure with headline, lead, body, and conclusion. "
     "Return ONLY the edited article text."),
    ("human", "Article to edit:\n{article}"),
])

PUBLISHER_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are a digital publisher. "
     "Format the article for publication: add a clear HEADLINE in ALL-CAPS on the first line, "
     "add a BYLINE saying By AI News Agency, add a DATELINE, "
     "and wrap the body in clean paragraphs separated by blank lines. "
     "Return ONLY the final formatted article."),
    ("human", "Edited article:\n{edited}"),
])

def writer_node(state: NewsState) -> NewsState:
    chain = WRITER_PROMPT | llm
    output = chain.invoke({"topic": state["topic"]})
    state["draft"] = output.content
    return state

def fact_checker_node(state: NewsState) -> NewsState:
    from tools import ddg
    try:
        results = ddg.invoke(state["topic"])
        search_text = "\n".join(
            f"[{r.get('title')}] {r.get('snippet')} ({r.get('link')})"
            for r in results
        )
    except Exception:
        search_text = "No search results available."

    chain = FACT_CHECKER_PROMPT | llm
    output = chain.invoke({
        "draft": state["draft"],
        "search_results": search_text
    })

    try:
        clean = output.content.replace("```json", "").replace("```", "").strip()
        state["fact_report"] = json.loads(clean)
    except Exception:
        state["fact_report"] = {
            "verdict": "pass",
            "issues": [],
            "revised_draft": ""
        }

    return state

def editor_node(state: NewsState) -> NewsState:
    report = state.get("fact_report") or {}
    article = report.get("revised_draft") or state["draft"]
    chain = EDITOR_PROMPT | llm
    output = chain.invoke({"article": article})
    state["edited"] = output.content
    return state

def publisher_node(state: NewsState) -> NewsState:
    chain = PUBLISHER_PROMPT | llm
    output = chain.invoke({"edited": state["edited"]})
    state["final"] = output.content
    return state

workflow = StateGraph(NewsState)

workflow.add_node("writer", writer_node)
workflow.add_node("fact_checker", fact_checker_node)
workflow.add_node("editor", editor_node)
workflow.add_node("publisher", publisher_node)

workflow.set_entry_point("writer")

workflow.add_edge("writer", "fact_checker")
workflow.add_edge("fact_checker", "editor")
workflow.add_edge("editor", "publisher")
workflow.add_edge("publisher", END)

graph = workflow.compile()

st.set_page_config(page_title="AI News Agency", layout="centered")

st.title("AI News Agency")
st.caption("Writer → Fact-Checker → Editor → Publisher")

if "messages" not in st.session_state:
    st.session_state.messages = []

col1, col2 = st.columns([4, 1])
with col2:
    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.rerun()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "user":
            st.markdown(message["content"])
        else:
            with st.expander("View Draft"):
                st.write(message.get("draft"))

            with st.expander("Fact Check Report"):
                st.write(message.get("fact_report"))

            with st.expander("Edited Version"):
                st.write(message.get("edited"))

            with st.expander("Final Published Version"):
                st.write(message.get("final"))

if topic := st.chat_input("Enter a news topic..."):

    st.session_state.messages.append({
        "role": "user",
        "content": topic
    })

    with st.chat_message("user"):
        st.markdown(topic)

    init_state: NewsState = {
        "topic": topic.strip(),
        "draft": None,
        "fact_report": None,
        "edited": None,
        "final": None,
        "error": None,
    }

    with st.spinner("Running newsroom pipeline..."):
        final_state = graph.invoke(init_state)

    final_article = final_state.get("final", "Something went wrong.")

    with st.chat_message("assistant"):
        with st.expander("View Draft"):
            st.write(final_state.get("draft"))

        with st.expander("Fact Check Report"):
            report = final_state.get("fact_report", {})

            verdict = report.get("verdict")
            issues = report.get("issues", [])
            revised = report.get("revised_draft")

            st.write(f"Verdict: {verdict}")

            if issues:
                st.write("Issues Found:")
                for issue in issues:
                    st.write(f"- {issue}")

            if revised:
                st.write("Revised Draft Provided")
                st.markdown(report["revised_draft"])

        with st.expander("Edited Version"):
            st.write(final_state.get("edited"))

        with st.expander("Final Published Version"):
            st.write(final_state.get("final"))

 
    st.session_state.messages.append({
        "role": "assistant",
        "draft": final_state.get("draft"),
        "fact_report": final_state.get("fact_report"),
        "edited": final_state.get("edited"),
        "final": final_state.get("final")
    })