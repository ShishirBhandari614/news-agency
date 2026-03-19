# 🗞 AI Newsroom — Upgraded Multi-Agent System

A LangGraph-powered newsroom with planning, research, conditional fact-checking, memory, and observability.

## Architecture

```
Planner → Researcher → Writer → Fact-Checker ──┐
                           ↑                    │ fail (≤2x)
                           └────────────────────┘
                                                │ pass
                                            Editor → Publisher
```

## New vs Old

| Feature | Before | After |
|---|---|---|
| Nodes | 4 (Writer→FC→Editor→Publisher) | 6 (Planner→Researcher→Writer→FC→Editor→Publisher) |
| State | 5 fields | 16 structured fields |
| Fact-check | Pass/fail + vague issues | Claim-by-claim: supported/weak/unsupported |
| Conditional flow | None | Loops back to Writer on fail (max 2x) |
| Memory | None | Short-term context + long-term JSON persistence |
| Observability | None | Timestamped execution log + file log |
| Research | Single query in FC node | Dedicated researcher with 3 targeted queries |
| Output formats | Article only | Article / Brief / Newsletter / Social |

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file:
```
OPENAI_API_KEY=your_key_here
```

Run:
```bash
streamlit run main.py
```

## File Structure

```
newsroom/
├── main.py          # Streamlit UI
├── graph.py         # LangGraph workflow + conditional edges
├── agents.py        # All node logic + prompts
├── state.py         # Structured TypedDict state
├── tools.py         # DuckDuckGo search + memory utilities
├── requirements.txt
└── README.md
```

## Memory

- **Short-term**: memory context injected into planner/writer/editor each run
- **Long-term**: `newsroom_memory.json` stores covered topics, run history, style preferences (persists across runs)
- Edit style preferences live from the sidebar

## Observability

- Execution log visible in the **Log** tab per article
- `newsroom_run.log` file written to disk with timestamps
- Each node logs entry/exit with key metrics
