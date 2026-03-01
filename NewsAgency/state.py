from typing import Optional, TypedDict

class NewsState(TypedDict):
    topic: str
    draft: Optional[str]
    fact_report: Optional[dict]   
    edited: Optional[str]
    final: Optional[str]
    error: Optional[str]