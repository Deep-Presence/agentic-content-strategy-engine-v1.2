from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class StyleGuideResearchInput(BaseModel):
    company_id: Optional[str] = Field(
        default=None,
        description="Supabase company UUID for mirroring style guide artifacts.",
    )
    company_name: str
    domain: Optional[str] = None
    company_slug: Optional[str] = Field(
        default=None, description="If omitted, derived from company_name."
    )
    company_context_path: Optional[str] = Field(
        default=None,
        description="Path to company context md (DeepAgents path, e.g. /artifacts/company_context/<slug>.md)",
    )
    persona_paths: List[str] = Field(
        default_factory=list,
        description="List of persona artifact paths (DeepAgents paths).",
    )
    internal_sources: List[str] = Field(
        default_factory=list, description="Paths to transcripts/notes"
    )
    language: str = "en"
    region: Optional[str] = None
    additional_constraints: Optional[str] = None


class WritingStyleGuideArtifact(BaseModel):
    company_name: str
    domain: Optional[str] = None
    voice_tone: str
    channel_variations: str
    show_vs_tell: str
    sentence_language: str
    jargon_rules: str
    audience_resonance: str
    product_positioning: str
    do_dont: str
    formatting_structure: str
    sample_snippets: str
    sources: List[str] = Field(default_factory=list)

    def to_markdown(self) -> str:
        lines: List[str] = [
            f"# Writing Style Guide: {self.company_name}",
            "",
            f"**Domain:** {self.domain or 'n/a'}",
            "",
            "## Voice & Tone",
            self.voice_tone,
            "## Channel Variations",
            self.channel_variations,
            "## Show vs Tell (Good/Bad Examples)",
            self.show_vs_tell,
            "## Sentence & Language Choices",
            self.sentence_language,
            "## Jargon / Terminology Rules",
            self.jargon_rules,
            "## Audience Resonance (from Personas)",
            self.audience_resonance,
            "## Product Positioning & Messaging Pillars",
            self.product_positioning,
            "## Do / Don't",
            self.do_dont,
            "## Formatting & Structure",
            self.formatting_structure,
            "## Sample Snippets",
            self.sample_snippets,
            "## Sources",
        ]
        if self.sources:
            lines.extend([f"- {s}" for s in self.sources])
        else:
            lines.append("- TBD")
        return "\n".join(lines)


