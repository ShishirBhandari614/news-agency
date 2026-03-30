# Sample Runs

Here is a walkthrough of what actually happens when you type a topic into the app. I wanted to show both the user-facing experience and what the agents are doing internally.

### Example: A Tech News Article

**What I typed into the UI:**

> "Write an article about the latest developments in AI regulation in 2025."

The Planner node processed that and produced this structured plan:

```json
{
  "plan": "Cover the current state of AI regulation globally, focusing on legislation passed or proposed in 2025.",
  "research_queries": [
    "AI regulation laws 2025",
    "EU AI Act implementation 2025",
    "US AI policy updates 2025"
  ],
  "required_sections": ["headline", "lead", "body", "conclusion"],
  "output_format": "article"
}
```

The Researcher then went and searched each of those queries, forcing the current year into every one. It also flagged if any results were outdated by writing a data warning at the top of its notes.

The Writer drafted the article using those notes. The Fact Checker then ran a separate search for each individual factual claim. For example, one claim might be "The EU AI Act entered into force in August 2024." The fact checker would specifically search for that sentence and look for evidence.

**Internal log from the Fact Checker:**

> FACT CHECKER verdict=pass | Issues=0 | Searches done=5

Since it passed, the article went straight to the Editor and then the Publisher.

**Final output (trimmed for brevity):**

---

AI REGULATION HITS A TURNING POINT IN 2025

By AI Newsroom
March 31, 2025

Governments around the world are moving faster than ever to put guardrails on artificial intelligence, with 2025 shaping up to be the most significant year for AI policy since the technology entered mainstream use.

The European Union's AI Act, which entered into force in mid-2024, began its first major compliance deadlines this year, requiring high-risk AI systems to meet strict transparency and safety requirements. Meanwhile, the United States, which has taken a more fragmented approach to AI regulation, saw renewed debate in Congress over whether a federal framework is needed.

According to available information, at least a dozen countries introduced or updated AI-related legislation in the first quarter of 2025 alone. The pace of regulatory activity reflects growing public concern about deepfakes, algorithmic bias, and the use of AI in critical infrastructure.

Experts say the challenge now is not whether to regulate, but how to do it without stifling innovation. "We are in a race between the technology and the rules meant to govern it," said one policy researcher at a think tank that monitors global AI governance.

---

*Note: Some details are still emerging as reporting on this topic is ongoing.*

---

### What Happened When Fact Checking Failed

In another test, I gave the app a topic with very little current data. The Fact Checker came back with a fail verdict because one of the claims could not be verified. It sent the draft back to the Writer with the issues logged. The Writer revised the article to soften the language around those claims, and on the second attempt the Fact Checker passed it.
