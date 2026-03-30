# Reflection

Building the AI Travel Planner was a huge learning experience for me. Here's a quick look back at why I made certain design choices, what blew up in my face, and what actually worked.

## Why I Chose LangGraph
I decided to use a LangGraph state machine purely out of frustration with standard LLM prompts. I noticed that if I asked ChatGPT to plan a trip, calculate a budget, check its own work, and print it out nicely, it would inevitably drop the ball on at least one constraint (usually the budget). 

By splitting the task up into specialized "agents" (Planner, Researcher, Builder, Reviewer) and passing a strict `TravelState` dictionary between them, I forced the AI to focus on one problem at a time. The biggest win from this architecture was my `Constraint Checker` node. Giving the AI the ability to grade its own draft and silently trigger a "rebuild loop" if it failed the budget check was incredibly powerful. It acts like an autonomous quality assurance layer.

## What Worked Well
- **Live web scraping**: Giving the AI hard data was a game changer. I set up a tool that uses `BeautifulSoup` to openly scrape Numbeo for exact prices (like the cost of a cappuccino or a taxi) in the target city. Grounding the Itinerary Builder in these real numbers entirely stopped the LLM from making up random, unrealistic budgets.
- **Long-term memory**: Hooking up LangGraph's `InMemoryStore` to power the "Preferences" side-panel worked perfectly. It's really satisfying to tell the app "I like fancy hotels" once, and then watch the Planner automatically weave that into every future trip.

## The Rough Patches
- **JSON Formatting Nightmares**: Getting the agents (`gpt-4o-mini`) to cleanly output parsing-ready JSON was endlessly annoying. Even with strict system prompts, the model would sometimes throw in conversational fluff like "Here is your JSON layout:" which would immediately crash the `json.loads()` parser. I had to write safety nets to strip away markdown backticks and catch exceptions everywhere.
- **Infinite Loops**: In my early tests, if I gave the app an impossible task (like 10 days in Paris on a $50 overall budget), the Constraint Checker would keep failing it, and the Builder would keep trying to rewrite it forever. I eventually had to introduce a strict `MAX_REBUILDS` counter to forcibly break out of the loop and just give the user the best attempt.

## What I'd Do Differently Next Time
If I had another few weeks to work on this, my first priority would be **streaming the output**. Right now, because the user has to wait for all 5 agents to finish their distinct jobs in sequence, they are stuck staring at a loading spinner for 15-30 seconds. I'd love to re-wire the Streamlit UI to stream the intermediate tokens live so the app feels much faster.

Secondly, I'd swap the `InMemoryStore` for a real SQLite or PostgreSQL database. Right now, if I completely stop the server, it forgets all of the long-term preferences. 
