AI News Agency — Multi-Agent System

This project is a LangChain and LangGraph based multi-agent system that simulates how a real news agency works. A user provides a topic, and the system moves that topic through a structured editorial workflow from draft to publication.

ARCHITECTURE:

The workflow follows a clear sequence. A user submits a topic. The Writer creates the first draft of the article. The Fact-Checker reviews the draft using web search to verify claims. The Editor refines the corrected draft for clarity and style. Finally, the Publisher formats the article for publication.

FILES:

state.py
Defines the NewsState TypedDict. This shared state object is passed between all agents so they can read and update the article as it progresses through the workflow.

tools.py
Contains the DuckDuckGo search tool used by the Fact-Checker to verify factual claims.

main.py
Includes all agent definitions, the LangGraph workflow configuration, and the Streamlit user interface.

AGENT ROLES:

Writer
Responsible for drafting a 300 to 400 word news article based on the provided topic.
Input: topic
Output: draft

Fact-Checker
Reviews the draft and verifies claims using web search results. Identifies factual issues and may provide a corrected version of the article.
Input: draft and search results
Output: fact_report in JSON format

Editor
Improves clarity, structure, grammar, and overall readability. If the Fact-Checker provides a revised draft, the Editor works from that corrected version.
Input: corrected draft
Output: edited article

Publisher
Formats the final edited article for publication.
Input: edited article
Output: final formatted article

Structured Data Exchange

The Fact-Checker always returns a structured JSON object containing a verdict, a list of issues if any are found, and a revised draft when corrections are necessary.

If the verdict is fail, the Editor automatically uses the revised draft to ensure factual corrections are carried forward. If the verdict is pass, the original draft moves to the Editor unchanged.

Setup and Running Locally

Clone the repository

git clone <your-repo-url>
cd news-agency

Create a .env file

Add your OpenAI API key:

OPENAI_API_KEY=sk-...

Install dependencies

pip install -r requirements.txt

Run the application

streamlit run main.py

Sample Execution

If the topic is “NASA's Artemis moon mission latest update,” the application will generate:

1. A first draft written by the Writer

2. A fact-check report with a pass or fail verdict

3. An edited version with improved clarity and grammar

4. A final published article formatted with a headline, byline, and dateline

