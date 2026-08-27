from __future__ import annotations

from grounding import GroundingBuilder
from models import StrategyProposal
from rag import KnowledgeSnippet


def test_grounding_builder_links_proposals_and_risk_to_rag_evidence() -> None:
    snippets = [
        KnowledgeSnippet(
            title="Urban Civilian Risk Control",
            content="civilian_dense operations require collateral damage controls",
            score=9.2,
            source="tactical_knowledge.md",
        ),
        KnowledgeSnippet(
            title="Low Intelligence Reconnaissance First",
            content="low_intel requires reconnaissance before commitment",
            score=8.1,
            source="tactical_knowledge.md",
        ),
    ]
    proposals = [
        StrategyProposal(
            agent_name="快速突击智能体",
            strategy_name="分阶段控制",
            summary="先控制通道，再压缩风险",
            actions=["保留疏散通道", "补充侦察"],
            metric_scores={},
            rationale="需要结合城市平民风险和低情报侦察证据",
            knowledge_sources=["Urban Civilian Risk Control"],
        )
    ]
    risk_context = {
        "risk_level": "high",
        "recommendations": ["优先控制附带损害", "先补充侦察和诱导试探"],
        "context_evidence": {
            "knowledge_titles": [
                "Urban Civilian Risk Control",
                "Low Intelligence Reconnaissance First",
            ],
            "signals": ["knowledge_civilian_risk", "knowledge_intel_gap"],
        },
    }

    report = GroundingBuilder().build(
        knowledge_context=snippets,
        proposals=proposals,
        risk_context=risk_context,
    )
    data = report.to_dict()

    assert data["status"] == "grounded"
    assert data["summary"]["knowledge_snippet_count"] == 2
    assert data["summary"]["grounded_proposal_count"] == 1
    assert data["proposal_grounding"][0]["grounded"] is True
    assert data["proposal_grounding"][0]["evidence"][0]["evidence_id"] == "rag-1"
    assert data["risk_grounding"]["evidence_titles"] == [
        "Urban Civilian Risk Control",
        "Low Intelligence Reconnaissance First",
    ]
    assert data["risk_grounding"]["recommendation_grounding"][0]["evidence_ids"] == ["rag-1", "rag-2"]
