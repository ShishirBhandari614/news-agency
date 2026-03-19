from typing import Optional, TypedDict, List


class ClaimCheck(TypedDict):
    claim: str
    status: str        # "supported" | "weak" | "unsupported"
    evidence: str


class FactReport(TypedDict):
    verdict: str       # "pass" | "fail"
    issues: List[str]
    claim_checks: List[ClaimCheck]
    revised_draft: str


class NewsState(TypedDict):
    # Input
    topic: str

    # Planner outputs
    plan: Optional[str]
    research_queries: Optional[List[str]]
    required_sections: Optional[List[str]]
    output_format: Optional[str]   # "article" | "brief" | "social" | "newsletter"

    # Research
    research_notes: Optional[str]
    extracted_claims: Optional[List[str]]

    # Writing
    draft: Optional[str]

    # Fact-checking
    fact_report: Optional[FactReport]
    revision_count: Optional[int]

    # Editing & publishing
    edited: Optional[str]
    final: Optional[str]

    # Memory & observability
    memory_context: Optional[str]
    execution_log: Optional[List[str]]

    # Control
    status: Optional[str]   # "planning"|"researching"|"writing"|"fact_checking"|"editing"|"done"|"error"
    error: Optional[str]
