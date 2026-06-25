"""Code-defined BYOK agent catalog."""
from __future__ import annotations

from enum import Enum
from typing import Iterable

from pydantic import BaseModel, Field


class AgentCapability(str, Enum):
    chat = "chat"
    structured_output = "structured_output"
    embeddings = "embeddings"
    deep_research = "deep_research"
    web_citations = "web_citations"


class AgentDefinition(BaseModel):
    agent_key: str = ""
    display_name: str = ""
    group: str = ""
    pipeline: str = ""
    pipeline_step: str = ""
    default_model: str = ""
    default_temperature: float | None = None
    default_max_tokens: int | None = None
    default_timeout_s: float | None = None
    capabilities: list[AgentCapability] = Field(default_factory=list)
    required: bool = True
    description: str = ""


def _settings():
    from core.config.settings import settings

    return settings


def _agent(
    agent_key: str,
    display_name: str,
    group: str,
    pipeline: str,
    pipeline_step: str,
    default_model: str,
    *,
    capabilities: Iterable[AgentCapability] = (AgentCapability.chat,),
    default_temperature: float | None = None,
    default_max_tokens: int | None = None,
    default_timeout_s: float | None = None,
    required: bool = True,
    description: str = "",
) -> AgentDefinition:
    return AgentDefinition(
        agent_key=agent_key,
        display_name=display_name,
        group=group,
        pipeline=pipeline,
        pipeline_step=pipeline_step,
        default_model=default_model,
        default_temperature=default_temperature,
        default_max_tokens=default_max_tokens,
        default_timeout_s=default_timeout_s,
        capabilities=list(capabilities),
        required=required,
        description=description,
    )


def all_agent_definitions() -> list[AgentDefinition]:
    s = _settings()
    chat = AgentCapability.chat
    structured = AgentCapability.structured_output
    embeddings = AgentCapability.embeddings
    deep_research = AgentCapability.deep_research
    web_citations = AgentCapability.web_citations

    definitions = [
        _agent(
            "shared.embeddings.default",
            "Default Embeddings",
            "Shared",
            "shared",
            "embeddings",
            s.embedding_model,
            capabilities=(embeddings,),
        ),
        _agent("gap.query_generation", "Query Generation", "Gap Analysis", "gap", "query_generation", s.gap_analysis_query_gen_model, capabilities=(chat, structured)),
        _agent("gap.report_generation", "Report Generation", "Gap Analysis", "gap", "report_generation", s.gap_analysis_report_model, capabilities=(chat, structured)),
        _agent("gap.search.perplexity", "Perplexity Search", "Gap Analysis", "gap", "search_perplexity", s.perplexity_search_model, capabilities=(chat, web_citations)),
        _agent("gap.search.openai", "OpenAI Search", "Gap Analysis", "gap", "search_openai", s.gap_analysis_openai_engine_model, capabilities=(chat, web_citations), required=False, description="Disabled in BYOK v1 unless OpenRouter search parity is implemented."),
        _agent("gap.search.claude", "Claude Search", "Gap Analysis", "gap", "search_claude", s.gap_analysis_claude_engine_model, capabilities=(chat, web_citations), required=False, description="Disabled in BYOK v1 unless OpenRouter search parity is implemented."),
        _agent("gap.search.gemini", "Gemini Search", "Gap Analysis", "gap", "search_gemini", s.gap_analysis_gemini_engine_model, capabilities=(chat, web_citations), required=False, description="Disabled in BYOK v1 unless OpenRouter search parity is implemented."),
        _agent("content.planner", "Planner", "Content Engine", "content", "planner", s.content_engine_planner_model, capabilities=(chat, structured)),
        _agent("content.strategic_planner", "Strategic Planner", "Content Engine", "content", "strategic_planner", s.content_engine_v13_planner_model, capabilities=(chat, structured)),
        _agent("content.brief_builder", "Brief Builder", "Content Engine", "content", "brief_builder", s.content_engine_v13_brief_builder_model, capabilities=(chat, structured)),
        _agent("content.worker.outliner", "Outliner", "Content Engine", "content", "worker_outliner", s.content_engine_worker_model, capabilities=(chat, structured)),
        _agent("content.worker.drafter", "Drafter", "Content Engine", "content", "worker_drafter", s.content_engine_worker_model, capabilities=(chat,)),
        _agent("content.worker.reviser", "Reviser", "Content Engine", "content", "worker_reviser", s.content_engine_worker_model, capabilities=(chat,)),
        _agent("content.worker.fact_enricher", "Fact Enricher", "Content Engine", "content", "worker_fact_enricher", s.content_engine_fact_enricher_model, capabilities=(chat, web_citations)),
        _agent("content.worker.linker", "Linker", "Content Engine", "content", "worker_linker", s.content_engine_v13_linker_model, capabilities=(chat, web_citations)),
        _agent("content.formatter", "Formatter", "Content Engine", "content", "formatter", s.content_engine_formatter_model, capabilities=(chat,)),
        _agent("content.judge.style", "Style Judge", "Content Engine", "content", "judge_style", s.content_engine_style_judge_model, capabilities=(chat, structured)),
        _agent("content.judge.factual", "Factual Judge", "Content Engine", "content", "judge_factual", s.content_engine_factual_judge_model, capabilities=(chat, structured)),
        _agent("content.judge.eeat", "E-E-A-T Judge", "Content Engine", "content", "judge_eeat", s.content_engine_v13_eeat_judge_model, capabilities=(chat, structured)),
        _agent("content.embedding.semantic", "Semantic Content Embeddings", "Content Engine", "content", "semantic_embedding", s.embedding_model, capabilities=(embeddings,)),
        _agent("topic_discovery.source_a_company", "Company Source", "Topic Discovery", "topic_discovery", "source_a_company", s.topic_discovery_brainstorm_model, capabilities=(chat, structured)),
        _agent("topic_discovery.source_b_persona", "Persona Source", "Topic Discovery", "topic_discovery", "source_b_persona", s.topic_discovery_brainstorm_model, capabilities=(chat, structured)),
        _agent("topic_discovery.source_c_deep_research", "Deep Research Source", "Topic Discovery", "topic_discovery", "source_c_deep_research", s.topic_discovery_source_c_model, capabilities=(chat, deep_research, web_citations), default_timeout_s=s.topic_discovery_source_c_timeout_s),
        _agent("topic_discovery.source_d_adversarial", "Adversarial Source", "Topic Discovery", "topic_discovery", "source_d_adversarial", s.topic_discovery_brainstorm_model, capabilities=(chat, structured)),
        _agent("topic_discovery.hierarchy_unified_s2", "Unified Hierarchy", "Topic Discovery", "topic_discovery", "hierarchy_unified_s2", s.topic_discovery_unified_s2_model, capabilities=(chat, structured)),
        _agent("topic_discovery.subdomain_expansion", "Subdomain Expansion", "Topic Discovery", "topic_discovery", "subdomain_expansion", s.topic_discovery_unified_s2_model, capabilities=(chat, structured), default_timeout_s=s.topic_discovery_expansion_timeout_s),
        _agent("topic_discovery.relevance_filter", "Relevance Filter", "Topic Discovery", "topic_discovery", "relevance_filter", s.topic_discovery_brainstorm_model, capabilities=(chat, structured)),
        _agent("topic_discovery.topic_generation", "Topic Generation", "Topic Discovery", "topic_discovery", "topic_generation", s.topic_discovery_brainstorm_model, capabilities=(chat, structured)),
        _agent("topic_discovery.dedup", "Deduplication", "Topic Discovery", "topic_discovery", "dedup", s.topic_discovery_dedup_model, capabilities=(chat, structured)),
        _agent("topic_discovery.cannibalization_embedding", "Cannibalization Embeddings", "Topic Discovery", "topic_discovery", "cannibalization_embedding", s.embedding_model, capabilities=(embeddings,)),
        _agent("research.kb.company_overview", "Company Overview", "Knowledge Base", "research_kb", "company_overview", s.research_kb_company_overview_model, capabilities=(chat, deep_research, web_citations)),
        _agent("research.kb.customer_reviews", "Customer Reviews", "Knowledge Base", "research_kb", "customer_reviews", s.research_kb_customer_reviews_model, capabilities=(chat, deep_research, web_citations)),
        _agent("research.kb.competitor_scanner", "Competitor Scanner", "Knowledge Base", "research_kb", "competitor_scanner", s.research_kb_competitor_scanner_model, capabilities=(chat, deep_research, web_citations)),
        _agent("research.kb.competitor_extractor", "Competitor Extractor", "Knowledge Base", "research_kb", "competitor_extractor", s.research_kb_competitor_extractor_model, capabilities=(chat, structured)),
        _agent("research.kb.weakness_analyst", "Weakness Analyst", "Knowledge Base", "research_kb", "weakness_analyst", s.research_kb_weakness_analyst_model, capabilities=(chat, deep_research, web_citations)),
        _agent("research.kb.brand_perception", "Brand Perception", "Knowledge Base", "research_kb", "brand_perception", s.research_kb_brand_perception_model, capabilities=(chat, structured)),
        _agent("research.kb.synthesis", "KB Synthesis", "Knowledge Base", "research_kb", "synthesis", s.research_kb_synthesis_model, capabilities=(chat, structured)),
        _agent("research.ap.suggester", "Persona Suggester", "Audience Persona", "research_ap", "suggester", s.audience_persona_suggester_model, capabilities=(chat, structured)),
        _agent("research.ap.profile_generator", "Persona Profile Generator", "Audience Persona", "research_ap", "profile_generator", s.audience_persona_generator_model, capabilities=(chat, deep_research, web_citations)),
        _agent("research.vsg.author_discovery", "Author Discovery", "Voice Style Guide", "research_vsg", "author_discovery", s.voice_style_guide_discovery_model, capabilities=(chat, web_citations)),
        _agent("research.vsg.author_research", "Author Research", "Voice Style Guide", "research_vsg", "author_research", s.perplexity_deep_research_model, capabilities=(chat, deep_research, web_citations)),
        _agent("research.vsg.synthesis", "Voice Synthesis", "Voice Style Guide", "research_vsg", "synthesis", s.voice_style_guide_synthesis_model, capabilities=(chat, structured)),
        _agent("daily_tracker.fanout", "Query Fanout", "Daily Tracker", "daily_tracker", "fanout", s.daily_tracker_fanout_model, capabilities=(chat, structured), default_temperature=s.daily_tracker_fanout_temperature),
        _agent("daily_tracker.content_to_prompt", "Content To Prompt", "Daily Tracker", "daily_tracker", "content_to_prompt", s.daily_tracker_fanout_model, capabilities=(chat, structured), default_temperature=s.daily_tracker_fanout_temperature),
        _agent("daily_tracker.platform.perplexity", "Perplexity Platform", "Daily Tracker", "daily_tracker", "platform_perplexity", s.perplexity_search_model, capabilities=(chat, web_citations)),
        _agent("daily_tracker.platform.openai", "OpenAI Platform", "Daily Tracker", "daily_tracker", "platform_openai", s.gap_analysis_openai_engine_model, capabilities=(chat, web_citations), required=False, description="Disabled in BYOK v1 unless OpenRouter search parity is implemented."),
        _agent("daily_tracker.platform.claude", "Claude Platform", "Daily Tracker", "daily_tracker", "platform_claude", s.gap_analysis_claude_engine_model, capabilities=(chat, web_citations), required=False, description="Disabled in BYOK v1 unless OpenRouter search parity is implemented."),
        _agent("daily_tracker.platform.gemini", "Gemini Platform", "Daily Tracker", "daily_tracker", "platform_gemini", s.gap_analysis_gemini_engine_model, capabilities=(chat, web_citations), required=False, description="Disabled in BYOK v1 unless OpenRouter search parity is implemented."),
        _agent("reddit_hil.ranking_drafting", "Ranking and Drafting", "Reddit HIL", "reddit_hil", "ranking_drafting", s.google_gemini_model_reddit_hil, capabilities=(chat, structured)),
    ]
    seen: set[str] = set()
    duplicates = [item.agent_key for item in definitions if item.agent_key in seen or seen.add(item.agent_key)]
    if duplicates:
        raise RuntimeError(f"Duplicate agent catalog keys: {', '.join(sorted(duplicates))}")
    return definitions


def get_agent_definition(agent_key: str) -> AgentDefinition | None:
    for definition in all_agent_definitions():
        if definition.agent_key == agent_key:
            return definition
    return None


def required_agents_for_pipeline(pipeline: str) -> list[AgentDefinition]:
    return [
        definition
        for definition in all_agent_definitions()
        if definition.pipeline == pipeline and definition.required
    ]


def required_agent_keys_for_onboarding() -> list[str]:
    """Return BYOK agent keys required by the onboarding meta-pipeline."""
    keys: list[str] = ["shared.embeddings.default"]
    for pipeline in (
        "research_kb",
        "research_ap",
        "research_vsg",
        "gap",
        "topic_discovery",
    ):
        keys.extend(
            definition.agent_key
            for definition in required_agents_for_pipeline(pipeline)
        )
    return list(dict.fromkeys(keys))
