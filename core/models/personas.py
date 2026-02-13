from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


PersonaKind = Literal["icp", "secondary"]


class PersonaResearchInput(BaseModel):
    company_id: Optional[str] = Field(
        default=None,
        description="Supabase company UUID (recommended for mirroring persona artifacts to Supabase).",
    )
    company_name: str
    domain: Optional[str] = None
    company_slug: Optional[str] = Field(
        default=None, description="If omitted, derived from company_name."
    )
    company_context_path: Optional[str] = Field(
        default=None,
        description="DeepAgents path to the company context md (e.g., /artifacts/company_context/acme.md). If omitted, derived from company_slug.",
    )
    internal_sources: List[str] = Field(
        default_factory=list, description="Paths to transcripts/notes"
    )
    max_personas: int = Field(
        default=3, ge=1, le=3, description="ICP + up to 2 secondary personas"
    )
    language: str = "en"
    region: Optional[str] = None
    additional_constraints: Optional[str] = None


class PersonaArtifact(BaseModel):
    company_name: str
    persona_name: str
    kind: PersonaKind = "icp"
    role_title: str
    industry_context: Optional[str] = None

    summary: str
    role_and_context: str
    day_in_life: str
    kpis_success: str
    pain_points_blockers: str
    buying_triggers: str
    trust_builders_objections: str
    annoyances: str
    messaging_angles: str
    quotes: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)

    def to_markdown(self) -> str:
        # Stable headers are important so future runs can patch specific sections.
        lines: List[str] = [
            f"# Persona: {self.persona_name} ({self.kind.upper()})",
            "",
            f"**Company:** {self.company_name}",
            f"**Role/Title:** {self.role_title}",
            f"**Industry context:** {self.industry_context or 'TBD'}",
            "",
            "## Persona Summary",
            self.summary,
            "## Role & Context",
            self.role_and_context,
            "## Day-in-the-Life Mechanics",
            self.day_in_life,
            "## KPIs / What Success Means",
            self.kpis_success,
            "## Pain Points & Blockers",
            self.pain_points_blockers,
            "## Buying Triggers",
            self.buying_triggers,
            "## Trust Builders & Objections",
            self.trust_builders_objections,
            "## Annoyances",
            self.annoyances,
            "## Messaging Angles",
            self.messaging_angles,
            "## Quotes",
        ]
        if self.quotes:
            lines.extend([f"- {q}" for q in self.quotes])
        else:
            lines.append("- TBD")
        lines.append("## Sources")
        if self.sources:
            lines.extend([f"- {s}" for s in self.sources])
        else:
            lines.append("- TBD")
        return "\n".join(lines)


