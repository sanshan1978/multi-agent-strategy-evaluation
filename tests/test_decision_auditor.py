from __future__ import annotations

from decision_auditor import RuleBasedDecisionAuditor
from main import PRESET_SCENES
from models import ScoredProposal, StrategyProposal


def test_decision_auditor_flags_high_risk_low_control() -> None:
    scene = PRESET_SCENES["urban_fast_capture"]
    proposal = StrategyProposal(
        agent_name="audit-agent",
        strategy_name="risky plan",
        summary="risky",
        actions=["move fast"],
        metric_scores={
            "success_prob": 80,
            "resource_efficiency": 60,
            "risk_control": 45,
            "response_speed": 90,
            "intel_alignment": 55,
        },
        rationale="fast but risky",
        confidence=0.5,
    )
    scored = ScoredProposal(proposal=proposal, weighted_score=70, final_score=80)

    audit = RuleBasedDecisionAuditor().audit(
        scene=scene,
        ranking=[scored],
        risk_context={
            "risk_level": "high",
            "risk_score": 80,
            "context_evidence": {
                "context_adjustment": 10,
                "signals": ["knowledge_civilian_risk"],
            },
        },
        knowledge_context=[],
        memory_context=[],
    )

    assert audit.overall_status == "attention_required"
    assert audit.finding_count >= 2
    codes = {finding.code for finding in audit.findings}
    assert "high_risk_low_control" in codes
    assert "civilian_safety_gap" in codes
    assert audit.evidence_summary["context_adjustment"] == 10


def test_decision_auditor_passes_low_risk_strong_plan() -> None:
    scene = PRESET_SCENES["plain_counterstrike"]
    proposal = StrategyProposal(
        agent_name="audit-agent",
        strategy_name="balanced plan",
        summary="balanced",
        actions=["advance"],
        metric_scores={
            "success_prob": 75,
            "resource_efficiency": 75,
            "risk_control": 82,
            "response_speed": 72,
            "intel_alignment": 80,
        },
        rationale="balanced plan",
        confidence=0.7,
    )
    scored = ScoredProposal(proposal=proposal, weighted_score=75, final_score=78)

    audit = RuleBasedDecisionAuditor().audit(
        scene=scene,
        ranking=[scored],
        risk_context={"risk_level": "low", "risk_score": 30, "context_evidence": {"context_adjustment": 0}},
        knowledge_context=[],
        memory_context=[],
    )

    assert audit.overall_status == "passed"
    assert audit.finding_count == 0
