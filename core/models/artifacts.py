from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl


class SourceDoc(BaseModel):
    id: str
    title: Optional[str] = None
    url: Optional[HttpUrl] = None
    source_type: str = Field(
        default="web", description="web|internal_transcript|note|other"
    )
    snippet: Optional[str] = None
    path: Optional[str] = Field(
        default=None, description="Filesystem path for local sources"
    )


class FactRow(BaseModel):
    claim: str
    evidence: str
    source_id: Optional[str] = None


class CompanyResearchInput(BaseModel):
    company_id: Optional[str] = Field(
        default=None,
        description="Supabase company UUID (recommended for mirroring artifacts to Supabase).",
    )
    auto_mirror: bool = Field(
        default=False,
        description="If True, mirror to Supabase automatically. If False, leave draft on FS for human approval.",
    )
    company_name: str
    domain: Optional[str] = None
    seed_urls: List[HttpUrl] = Field(default_factory=list, description="List of seed URLs to research.")
    internal_sources: List[str] = Field(
        default_factory=list, description="Paths to transcripts/notes"
    )
    language: str = "en"
    region: Optional[str] = None
    additional_constraints: Optional[str] = None


class CompanyContextArtifact(BaseModel):
    company_name: str
    domain: Optional[str] = None
    origin_story: Optional[str] = None
    products_services: Optional[str] = None
    market_positioning: Optional[str] = None
    target_audience: Optional[str] = None
    brand_perception: Optional[str] = None
    competitors: Optional[str] = None
    growth_drivers: Optional[str] = None
    bottlenecks: Optional[str] = None
    goals_urgency: Optional[str] = None
    risks_unknowns: Optional[str] = None
    recommendations: Optional[str] = None
    fact_table: List[FactRow] = Field(default_factory=list)
    open_questions: List[str] = Field(default_factory=list)
    sources: List[SourceDoc] = Field(default_factory=list)

    def to_markdown(self) -> str:
        fact_lines = [
            f"- {row.claim} — _{row.evidence}_ ({row.source_id or 'n/a'})"
            for row in self.fact_table
        ]
        sources_lines = [
            f"- [{src.id}] {src.title or ''} {src.url or src.path or ''} ({src.source_type})"
            for src in self.sources
        ]
        md = [
            f"# Company Context: {self.company_name}",
            "",
            f"**Domain:** {self.domain or 'n/a'}",
            "",
            "## Origin Story",
            self.origin_story or "TBD",
            "## Products & Services",
            self.products_services or "TBD",
            "## Market Positioning",
            self.market_positioning or "TBD",
            "## Target Audience",
            self.target_audience or "TBD",
            "## Brand Perception",
            self.brand_perception or "TBD",
            "## Competitors",
            self.competitors or "TBD",
            "## Growth Drivers",
            self.growth_drivers or "TBD",
            "## Bottlenecks",
            self.bottlenecks or "TBD",
            "## Goals & Urgency",
            self.goals_urgency or "TBD",
            "## Risks / Unknowns",
            self.risks_unknowns or "TBD",
            "## Recommendations",
            self.recommendations or "TBD",
            "## Fact Table",
            *(fact_lines or ["- TBD"]),
            "## Open Questions",
            *(["- " + q for q in self.open_questions] or ["- TBD"]),
            "## Sources",
            *(sources_lines or ["- TBD"]),
        ]
        return "\n".join(md)

