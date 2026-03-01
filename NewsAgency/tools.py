from langchain_community.tools import DuckDuckGoSearchResults

ddg = DuckDuckGoSearchResults(max_results=5, output_format="list")