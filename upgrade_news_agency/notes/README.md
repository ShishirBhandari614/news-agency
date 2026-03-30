# AI Newsroom

Hi! Welcome to my AI Newsroom project. This is a multi-agent application I built using LangGraph and Streamlit. The idea is simple: instead of just asking a single AI to write a news article, I set up a full editorial pipeline where different agents each play a specific role, just like a real newsroom.

You type in a topic, and the system plans, researches, writes, fact-checks, edits, and publishes a complete news article for you.

---

## How It Works

I used LangGraph to build a State Graph. A central `NewsState` dictionary gets passed from one agent to the next. Each agent reads what it needs, does its job, and writes its output back into the state before passing it along.

Here is the general flow:

```
User Input -> Planner -> Researcher -> Writer -> Fact Checker -> Editor -> Publisher
                                          ^              |
                                          |   (If fails) |
                                          +--------------+
```

The Fact Checker is the only node that can loop back. If it finds unsupported claims in the draft, it sends the article back to the Writer to try again. This loop can happen at most twice before it gives up and moves on anyway.

### The Agents

1. Planner: Reads the topic and figures out what kind of article to write (breaking news, in-depth, newsletter, or social posts). It also generates specific research queries and decides which sections the article needs.

2. Researcher: Takes those queries and searches the web using Tavily as the main search engine, with DuckDuckGo as a fallback. It also forces every query to include the current year so results stay fresh and relevant.

3. Writer: Uses the research notes and the plan to write a full first draft. The format depends on what the Planner decided (a short brief, a long article, a newsletter, etc.).

4. Fact Checker: This one is interesting. Instead of doing one broad search, it searches specifically for each individual claim extracted by the Researcher. That way, every factual statement in the article gets its own dedicated evidence check.

5. Editor: Cleans up the approved draft for grammar, flow, and clarity without changing any of the facts.

6. Publisher: Formats the final article for output, makes sure the dateline is today's date, and saves everything to long-term memory.

---

## Memory

I set up two layers of memory:

- Short-term (per chat): LangGraph's MemorySaver checkpointer handles this. Every chat session gets its own thread ID, so you can switch between topics and come back to them later.
- Long-term (across all chats): I used InMemoryStore for this. The system saves the writing tone, preferred article length, every topic it has covered, and full article contexts. The next time you cover a related topic, the Planner can reference what was written before and build on it.

---

## How to Run

**1. Set up a virtual environment and install dependencies:**

```command prompt
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

```if mac (terminal)
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**2. Set up your API Keys:**

Create a `.env` file in the project folder with your `OPENAI_API_KEY` and `TAVILY_API_KEY`.

**3. Run the app:**

```command prompt
streamlit run main.py
```

---

## Limitations

- All memory is in-process and in-memory. If the server restarts, everything resets. A real database would fix this.
- The fact-checker is still an LLM evaluating an LLM, so it is not perfect. It can miss things or be too lenient.
- Generating a full article through six consecutive nodes takes around 20-40 seconds depending on the topic.
