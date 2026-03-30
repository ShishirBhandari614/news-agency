from typing import Optional, TypedDict, List

class ClaimCheck(TypedDict):
    claim: str
    status: str        
    evidence: str

class FactReport(TypedDict):
    verdict: str       
    issues: List[str]
    claim_checks: List[ClaimCheck]
    revised_draft: str

class NewsState(TypedDict):
    
    topic: str

    plan: Optional[str]
    research_queries: Optional[List[str]]
    required_sections: Optional[List[str]]
    output_format: Optional[str]   

    research_notes: Optional[str]
    extracted_claims: Optional[List[str]]

    draft: Optional[str]

    fact_report: Optional[FactReport]
    revision_count: Optional[int]

    edited: Optional[str]
    final: Optional[str]

    memory_context: Optional[str]
    execution_log: Optional[List[str]]

    status: Optional[str]   
    error: Optional[str]

