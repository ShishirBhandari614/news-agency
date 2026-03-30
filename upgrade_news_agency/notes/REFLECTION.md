# Reflection

This project pushed me to think about AI systems very differently than I had before. Here is an honest look back at what went into the design, what surprised me, and what I would change.

## Why I Built It This Way

My starting point was a simple frustration. If you ask a regular LLM to write a news article, it tends to confidently state things that are either outdated or just made up. There is no awareness of the current date, no real searching, and no one checking the facts before anything gets published.

I chose LangGraph and a multi-agent state graph because it gave me control over the order and quality of every step. By splitting things up into a Planner, Researcher, Writer, Fact Checker, Editor, and Publisher, I could enforce that each stage only runs after the previous one has produced real output. The LLM is not trying to do everything at once, which leads to much better results.

The most deliberate design decision was how I handled the Fact Checker. Rather than doing one broad topic search, I made it search for each extracted claim individually. That felt closer to how a real fact-checker actually works: you verify specific statements, not just the general topic area.

## What Worked Well

The per-claim fact checking was genuinely effective. In my tests, the system caught several cases where the Writer had stated something just slightly too confidently based on thin evidence.

Forcing the current year into every search query also made a big difference. Early versions of the Researcher would pull search results from 2022 or 2023 and present them as current news. Adding a hard rule to rewrite every query with the current year fixed that almost completely.

The conditional loop between the Fact Checker and the Writer also worked better than I expected. Watching the system silently detect a problem, send the article back, and get a cleaner version on the second attempt felt like real quality control happening automatically.

## What Was Difficult

Getting consistent JSON output from the LLM was the most annoying part of the whole project. Even with very strict system prompts telling the model to return only valid JSON, it would sometimes add extra text before or after the JSON block. I had to write cleaning logic everywhere and wrap every parse attempt in a try-except block with sensible defaults.

Another challenge was time. Six consecutive LLM calls means the user can wait 30-40 seconds for a result. That is a long time to stare at a loading spinner. I worked around it by showing a live pipeline progress bar so at least the user can see which agent is currently running.

The year awareness was also trickier than I expected. Even after I forced the year into every query, the Researcher would sometimes still summarize old facts without clearly labeling them as old. I had to add explicit rules to the system prompt telling it to include the source year next to every key fact it wrote down.

## What I Would Improve

The biggest thing I would change is the memory system. Right now, everything is stored in an in-process dictionary that gets wiped every time the server restarts. For anything beyond a demo, I would swap this for a proper database like PostgreSQL or even SQLite so user history, covered topics, and style preferences actually persist.

I would also look into streaming the output token by token. Right now the whole pipeline runs in the background and the final result just appears all at once. Streaming intermediate output would make the app feel dramatically faster even if the total generation time is the same.

Finally, I would give the Fact Checker access to more reliable sources. Right now it is just using DuckDuckGo and Tavily search snippets, which are helpful but not the same as cross-referencing against actual news databases or primary sources.
