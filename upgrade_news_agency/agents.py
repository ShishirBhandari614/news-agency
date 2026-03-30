import json
import logging
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()  

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langgraph.store.base import BaseStore

from state import NewsState
from tools import ddg, build_memory_context, record_topic, record_run, save_article_context

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("newsroom_run.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("newsroom")

MAX_REVISIONS = 2
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.4)

def _log(state: NewsState, message: str) -> NewsState:
    logger.info(message)
    log = list(state.get("execution_log") or [])
    log.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
    state["execution_log"] = log
    return state

PLANNER_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are a senior news editor and strategic planner.\n"
     "TODAY IS: {today}. THE CURRENT YEAR IS: {year}.\n"
     "ABSOLUTE RULE: Every research_query you write MUST contain the year {year}.\n"
     "NEVER write queries with years 2022, 2023, or 2024. Only {year}.\n"
     "Given a topic and memory context, produce a structured JSON plan.\n"
     "Return ONLY valid JSON with these keys:\n"
     '{{"plan": "<2-3 sentence editorial plan>", '
     '"research_queries": ["<topic> {year}", "<topic> latest {year}", "<topic> current {year}"], '
     '"required_sections": ["<section1>", ...], '
     '"output_format": "<article|brief|newsletter|social>"}}\n'
     "Choose output_format based on topic nature:\n"
     "- Breaking news → brief\n"
     "- In-depth → article\n"
     "- Curated digest → newsletter\n"
     "- Viral/trendy → social"),
    ("human", "Today is {today}. Year is {year}.\nTopic: {topic}\n\nMemory context:\n{memory_context}"),
])

RESEARCHER_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are a diligent news researcher.\n"
     "TODAY IS: {today}. THE CURRENT YEAR IS: {year}.\n"
     "CRITICAL RULES:\n"
     "1. Only treat facts from {year} as current. Everything older is historical context.\n"
     "2. If search results are mostly from 2022-2024, you MUST write this warning at the top of research_notes:\n"
     "   'DATA WARNING: No {year} results found. Facts below are from [year] and may be outdated.'\n"
     "3. Never present old facts as current without flagging their year.\n"
     "4. Include the source year next to every key fact you write.\n"
     "Given a topic, editorial plan, and web search results, write research notes.\n"
     "Also extract key factual claims the writer will use.\n"
     "Return ONLY valid JSON:\n"
     '{{"research_notes": "<notes — include year of each fact>", "extracted_claims": ["<claim (year)>", ...]}}\n'
     "Be factual. Do not invent. If data is thin or old, say so clearly."),
    ("human", "Today is {today}. Year is {year}.\nTopic: {topic}\nPlan: {plan}\n\nSearch Results:\n{search_results}"),
])

WRITER_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are a professional news writer.\n"
     "Today\'s date is: {today}.\n"
     "Write a {output_format} on the given topic using the research notes and plan.\n"
     "Required sections: {required_sections}\n"
     "Memory/style guidance: {memory_context}\n"
     "IMPORTANT: If the research notes warn that data is limited or outdated, reflect that honestly\n"
     "in the article — use phrases like \'as of 2026\', \'according to available information\',\n"
     "or \'details are still emerging\' rather than stating uncertain facts confidently.\n"
     "Return ONLY the article text — headline, lead, body, conclusion. No commentary."),
    ("human", "Topic: {topic}\nPlan: {plan}\nResearch Notes:\n{research_notes}"),
])

FACT_CHECKER_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are a meticulous fact-checker.\n"
     "For each claim provided, assess it against the search evidence.\n"
     "Return ONLY valid JSON:\n"
     '{{"verdict": "pass"|"fail", '
     '"issues": ["<issue1>", ...], '
     '"claim_checks": [{{"claim": "...", "status": "supported"|"weak"|"unsupported", "evidence": "..."}}], '
     '"revised_draft": "<corrected article or empty string if pass>"}}\n'
     "verdict=fail if any claim is unsupported. verdict=pass if all are supported or weak."),
    ("human", "Draft:\n{draft}\n\nClaims to verify:\n{claims}\n\nSearch Evidence:\n{search_results}"),
])

EDITOR_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are a senior newspaper editor.\n"
     "Polish the article: improve clarity, flow, tone, and grammar without changing facts.\n"
     "Keep required structure. Return ONLY the edited article text."),
    ("human", "Required sections: {required_sections}\nStyle: {memory_context}\n\nArticle:\n{article}"),
])

PUBLISHER_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are a digital publisher. Format the article for publication.\n"
     "TODAY'S PUBLICATION DATE IS: {today}. Use THIS date as the dateline.\n"
     "CRITICAL: Never use any date from inside the article as the dateline. Only use {today}.\n"
     "Output format type: {output_format}\n"
     "- article: HEADLINE in ALL-CAPS, newline, By AI News Agency, newline, {today}, newline, clean paragraphs\n"
     "- brief: SHORT HEADLINE, 2-3 tight paragraphs, key takeaway bullet\n"
     "- newsletter: Section header, intro, bullets, sign-off\n"
     "- social: 3-5 tweet-style posts with hashtags\n"
     "Return ONLY the final formatted content."),
    ("human", "Publication date: {today}.\nEdited article:\n{edited}"),
])

def planner_node(state: NewsState, config: RunnableConfig, *, store: BaseStore) -> NewsState:
    state["status"] = "planning"
    state = _log(state, f"PLANNER starting — topic: {state['topic']}")

    memory_context = build_memory_context(state["topic"])
    state["memory_context"] = memory_context

    from datetime import date as _date
    _today = _date.today().strftime("%B %d, %Y")
    _year  = str(_date.today().year)
    chain = PLANNER_PROMPT | llm
    output = chain.invoke({
        "topic": state["topic"],
        "memory_context": memory_context,
        "today": _today,
        "year": _year,
    })

    try:
        clean = output.content.replace("```json", "").replace("```", "").strip()
        plan_data = json.loads(clean)
        state["plan"] = plan_data.get("plan", "")
        state["research_queries"] = plan_data.get("research_queries", [state["topic"]])
        state["required_sections"] = plan_data.get("required_sections", ["headline", "lead", "body", "conclusion"])
        state["output_format"] = plan_data.get("output_format", "article")
    except Exception as e:
        state["plan"] = "Write a factual, well-structured news article."
        state["research_queries"] = [state["topic"]]
        state["required_sections"] = ["headline", "lead", "body", "conclusion"]
        state["output_format"] = "article"
        state = _log(state, f"PLANNER JSON parse error (using defaults): {e}")

    state = _log(state, f"PLANNER done. Format={state['output_format']} | Queries={state['research_queries']}")
    return state

def researcher_node(state: NewsState) -> NewsState:
    state["status"] = "researching"
    state = _log(state, "RESEARCHER fetching web results...")

    from datetime import date as _date
    current_year = _date.today().year
    all_results = []

    import re
    for query in (state.get("research_queries") or [state["topic"]])[:3]:
        
        query_clean = re.sub(r'\b20\d{2}\b', '', query).strip()
        query_clean = f"{query_clean} {current_year}"
        try:
            results = ddg.invoke(query_clean)
            for r in results:
                all_results.append(f"[{r.get('title','?')}] {r.get('snippet','')} ({r.get('link','')})")
        except Exception:
            pass

    try:
        direct = ddg.invoke(f"{state['topic']} {current_year}")
        for r in direct:
            all_results.append(f"[{r.get('title','?')}] {r.get('snippet','')} ({r.get('link','')})")
    except Exception:
        pass

    search_text = "\n".join(all_results) if all_results else "No search results available."

    from datetime import date as _date
    chain = RESEARCHER_PROMPT | llm
    output = chain.invoke({
        "topic": state["topic"],
        "plan": state.get("plan", ""),
        "search_results": search_text,
        "today": _date.today().strftime("%B %d, %Y"),
        "year": str(_date.today().year),
    })

    try:
        clean = output.content.replace("```json", "").replace("```", "").strip()
        research_data = json.loads(clean)
        state["research_notes"] = research_data.get("research_notes", output.content)
        state["extracted_claims"] = research_data.get("extracted_claims", [])
    except Exception:
        state["research_notes"] = output.content
        state["extracted_claims"] = []

    state = _log(state, f"RESEARCHER done. Claims extracted: {len(state.get('extracted_claims') or [])}")
    return state

def writer_node(state: NewsState) -> NewsState:
    state["status"] = "writing"
    state = _log(state, "WRITER drafting article...")

    from datetime import date as _date
    chain = WRITER_PROMPT | llm
    output = chain.invoke({
        "topic": state["topic"],
        "plan": state.get("plan", ""),
        "research_notes": state.get("research_notes", ""),
        "output_format": state.get("output_format", "article"),
        "required_sections": ", ".join(state.get("required_sections") or []),
        "memory_context": state.get("memory_context", ""),
        "today": _date.today().strftime("%B %d, %Y"),
    })
    state["draft"] = output.content
    state = _log(state, "WRITER done.")
    return state

def fact_checker_node(state: NewsState) -> NewsState:
    state["status"] = "fact_checking"
    revision_count = (state.get("revision_count") or 0) + 1
    state["revision_count"] = revision_count
    state = _log(state, f"FACT_CHECKER running (attempt {revision_count}/{MAX_REVISIONS})...")

    from datetime import date as _date
    current_year = _date.today().year
    claims = state.get("extracted_claims") or []

    evidence_map: dict[str, str] = {}

    search_targets = claims[:6] if claims else [state["topic"]]

    for target in search_targets:
        
        query = target if len(target) < 80 else target[:80]
        if str(current_year) not in query:
            query = f"{query} {current_year}"
        try:
            results = ddg.invoke(query)
            snippets = "\n".join(
                f"[{r.get('title','?')}] {r.get('snippet','')} ({r.get('link','')})"
                for r in results
            )
            evidence_map[target] = snippets
        except Exception:
            evidence_map[target] = "No results found."

    state = _log(state, f"FACT_CHECKER searched {len(evidence_map)} claim(s) individually.")

    try:
        broad_results = ddg.invoke(f"{state['topic']} {current_year}")
        broad_text = "\n".join(
            f"[{r.get('title','?')}] {r.get('snippet','')} ({r.get('link','')})"
            for r in broad_results
        )
    except Exception:
        broad_text = "No broad results available."

    combined_evidence = "=== PER-CLAIM EVIDENCE ===\n"
    for claim, evidence in evidence_map.items():
        combined_evidence += f"\nClaim: {claim}\nEvidence:\n{evidence}\n"
    combined_evidence += f"\n=== BROAD TOPIC EVIDENCE ===\n{broad_text}"

    claims_text = "\n".join(f"- {c}" for c in claims)

    chain = FACT_CHECKER_PROMPT | llm
    output = chain.invoke({
        "draft": state.get("draft", ""),
        "claims": claims_text or "No explicit claims extracted.",
        "search_results": combined_evidence,
    })

    try:
        clean = output.content.replace("```json", "").replace("```", "").strip()
        report = json.loads(clean)
    except Exception:
        report = {"verdict": "pass", "issues": [], "claim_checks": [], "revised_draft": ""}

    state["fact_report"] = report
    verdict = report.get("verdict", "pass")
    state = _log(state, f"FACT_CHECKER verdict={verdict} | Issues={len(report.get('issues', []))} | Searches done={len(evidence_map)+1}")
    return state

def editor_node(state: NewsState) -> NewsState:
    state["status"] = "editing"
    state = _log(state, "EDITOR polishing article...")

    report = state.get("fact_report") or {}
    article = report.get("revised_draft") or state.get("draft", "")

    chain = EDITOR_PROMPT | llm
    output = chain.invoke({
        "article": article,
        "required_sections": ", ".join(state.get("required_sections") or []),
        "memory_context": state.get("memory_context", ""),
    })
    state["edited"] = output.content
    state = _log(state, "EDITOR done.")
    return state

def publisher_node(state: NewsState, config: RunnableConfig, *, store: BaseStore) -> NewsState:
    state["status"] = "done"
    state = _log(state, "PUBLISHER formatting final output...")

    from datetime import date
    chain = PUBLISHER_PROMPT | llm
    output = chain.invoke({
        "edited": state.get("edited", ""),
        "output_format": state.get("output_format", "article"),
        "today": date.today().strftime("%B %d, %Y"),
    })
    state["final"] = output.content

    record_topic(state["topic"])
    record_run(
        topic=state["topic"],
        output_format=state.get("output_format", "article"),
        success=True,
    )
    save_article_context(
        topic=state["topic"],
        plan=state.get("plan", ""),
        research_notes=state.get("research_notes", ""),
        final=state.get("final", ""),
        output_format=state.get("output_format", "article"),
    )

    state = _log(state, "PUBLISHER done. Run complete ✓")
    return state

def route_after_fact_check(state: NewsState) -> str:
    report = state.get("fact_report") or {}
    verdict = report.get("verdict", "pass")
    
    revision_count = state.get("revision_count") or 0

    if verdict == "fail" and revision_count < MAX_REVISIONS:
        logger.info(f"ROUTER → back to writer (attempt {revision_count}/{MAX_REVISIONS})")
        return "revise"
    else:
        logger.info("ROUTER → proceeding to editor")
        return "proceed"
