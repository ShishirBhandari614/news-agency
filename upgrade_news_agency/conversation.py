"""
conversation.py
---------------
Conversational agent for follow-up Q&A over generated articles.

Uses a messages list (same pattern as the deepagents example) so the LLM
sees the full conversation history on every turn. The MemorySaver checkpointer
persists this history per thread_id, so it survives across Streamlit reruns.

Token safety:
- Article context is injected ONCE as a system message at conversation start
- Only the conversation messages grow with each turn (not the article again)
- History is capped at MAX_HISTORY turns to prevent unbounded growth
"""

from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI
from tools import get_last_article, get_style_prefs

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.4)

# Cap conversation history to prevent token bloat.
# Each turn = 2 messages (user + assistant), so 10 turns = 20 messages max.
MAX_HISTORY = 20


def _build_system_prompt(article: dict | None) -> str:
    """Build the system prompt, injecting the article context once."""
    prefs = get_style_prefs()
    tone = prefs.get("tone", "professional and factual")

    base = (
        f"You are a helpful editorial assistant for the AI Newsroom.\n"
        f"Answer questions about the article that was just generated.\n"
        f"Tone: {tone}\n"
        f"Be concise and direct. If asked to rewrite or improve something, do it fully.\n"
    )

    if article:
        base += (
            f"\n--- ARTICLE CONTEXT ---\n"
            f"Topic: {article.get('topic', '?')}\n"
            f"Format: {article.get('output_format', 'article')}\n\n"
            f"Research notes:\n{article.get('research_notes', 'N/A')}\n\n"
            f"Final published article:\n{article.get('final', 'N/A')}\n"
            f"--- END ARTICLE CONTEXT ---\n"
        )
    else:
        base += "\nNo article has been generated yet in this session."

    return base


def run_followup(user_message: str, conv_messages: list) -> tuple[str, list]:
    """
    Send a follow-up question to the conversational agent.

    Args:
        user_message:  The user's question or instruction.
        conv_messages: The existing conversation history (list of role/content dicts).
                       This is stored in Streamlit session_state and passed in each time.

    Returns:
        (assistant_reply, updated_conv_messages)

    Token strategy:
        - System message contains article context (sent every time but only once per messages list)
        - conv_messages grows by 2 per turn (user + assistant)
        - Capped at MAX_HISTORY messages to prevent unbounded growth
        - Article context is NOT re-appended on every turn
    """
    article = get_last_article()
    system_prompt = _build_system_prompt(article)

    # Build the full messages list to send to the LLM:
    # [system] + [conversation history] + [new user message]
    messages_to_send = (
        [{"role": "system", "content": system_prompt}]
        + conv_messages
        + [{"role": "user", "content": user_message}]
    )

    response = llm.invoke(messages_to_send)
    assistant_reply = response.content

    # Update history: append user + assistant turn
    updated = conv_messages + [
        {"role": "user",      "content": user_message},
        {"role": "assistant", "content": assistant_reply},
    ]

    # Cap history to MAX_HISTORY messages to keep tokens bounded.
    # Always drop from the oldest end (keep most recent context).
    if len(updated) > MAX_HISTORY:
        updated = updated[-MAX_HISTORY:]

    return assistant_reply, updated


def detect_intent(user_input: str, has_articles: bool) -> str:
    """
    Use a fast LLM call to classify the user's input as:
      - 'new_topic'  → run the full pipeline
      - 'followup'   → route to conversational agent

    If no articles have been generated yet, always returns 'new_topic'.
    """
    if not has_articles:
        return "new_topic"

    prompt = (
        "You are a router for a news generation system.\n"
        "Classify the user input as either 'new_topic' or 'followup'.\n\n"
        "'new_topic' = the user wants to generate a brand new article on a fresh subject.\n"
        "'followup'  = the user is asking a question about, or requesting changes to, "
        "an article that was already generated (e.g. 'make it shorter', 'who were the sources', "
        "'rewrite the conclusion', 'summarise this', 'what did it say about X').\n\n"
        "Reply with ONLY one word: new_topic or followup.\n\n"
        f"User input: {user_input}"
    )

    result = llm.invoke([{"role": "user", "content": prompt}])
    intent = result.content.strip().lower()

    return "followup" if "followup" in intent else "new_topic"
