from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from memory import MemoryCase
from models import BattlefieldScene, ScoredProposal
from rag import KnowledgeSnippet


SEVERITY_ORDER = {"low": 1, "medium": 2, "high": 3}


@dataclass(frozen=True)
class AuditFinding:
    code: str
    severity: str
    message: str
    recommendation: str
    affected_agent: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "recommendation": self.recommendation,
            "affected_agent": self.affected_agent,
        }


@dataclass(frozen=True)
class DecisionAudit:
    overall_status: str
    checked_agent: str
    checked_strategy: str
    finding_count: int
    findings: List[AuditFinding] = field(default_factory=list)
    evidence_summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_status": self.overall_status,
            "checked_agent": self.checked_agent,
            "checked_strategy": self.checked_strategy,
            "finding_count": self.finding_count,
            "findings": [finding.to_dict() for finding in self.findings],
            "evidence_summary": self.evidence_summary,
        }


class RuleBasedDecisionAuditor:
    def audit(
        self,
        scene: BattlefieldScene,
        ranking: List[ScoredProposal],
        risk_context: Dict[str, Any],
        knowledge_context: List[KnowledgeSnippet],
        memory_context: List[MemoryCase],
    ) -> DecisionAudit:
        if not ranking:
            return DecisionAudit(
                overall_status="blocked",
                checked_agent="",
                checked_strategy="",
                finding_count=1,
                findings=[
                    AuditFinding(
                        code="missing_ranking",
                        severity="high",
                        message="No scored proposals are available for audit.",
                        recommendation="Regenerate proposals before finalizing the decision.",
                    )
                ],
                evidence_summary=self._evidence_summary(risk_context, knowledge_context, memory_context),
            )

        best = ranking[0]
        proposal = best.proposal
        scores = proposal.normalized_metric_scores()
        findings: List[AuditFinding] = []

        risk_level = str(risk_context.get("risk_level", "unknown"))
        context_evidence = risk_context.get("context_evidence", {})
        context_adjustment = _number(context_evidence.get("context_adjustment"), default=0.0)

        if risk_level == "high" and scores.get("risk_control", 0.0) < 65:
            findings.append(
                AuditFinding(
                    code="high_risk_low_control",
                    severity="high",
                    message="Top proposal has limited risk-control score under high-risk context.",
                    recommendation="Add explicit risk mitigation actions or compare against a defensive alternative.",
                    affected_agent=proposal.agent_name,
                )
            )

        if scene.civilian_presence >= 70 and scores.get("risk_control", 0.0) < 70:
            findings.append(
                AuditFinding(
                    code="civilian_safety_gap",
                    severity="high",
                    message="Civilian density is high but the top proposal does not strongly control collateral risk.",
                    recommendation="Prioritize evacuation corridors, precision reconnaissance, and staged control actions.",
                    affected_agent=proposal.agent_name,
                )
            )

        if scene.intel_quality < 60 and scores.get("intel_alignment", 0.0) < 68:
            findings.append(
                AuditFinding(
                    code="intel_alignment_gap",
                    severity="medium",
                    message="Intelligence quality is constrained and the top proposal has weak intel alignment.",
                    recommendation="Require reconnaissance-first validation before committing to high-tempo execution.",
                    affected_agent=proposal.agent_name,
                )
            )

        if context_adjustment >= 8:
            findings.append(
                AuditFinding(
                    code="context_risk_amplified",
                    severity="medium",
                    message="RAG or memory evidence materially increased the assessed risk.",
                    recommendation="Review context_evidence before treating the top proposal as final.",
                    affected_agent=proposal.agent_name,
                )
            )

        if proposal.confidence < 0.55:
            findings.append(
                AuditFinding(
                    code="low_agent_confidence",
                    severity="low",
                    message="Top proposal confidence is relatively low.",
                    recommendation="Ask the proposing agent to provide a contingency branch or stronger rationale.",
                    affected_agent=proposal.agent_name,
                )
            )

        return DecisionAudit(
            overall_status=self._overall_status(findings),
            checked_agent=proposal.agent_name,
            checked_strategy=proposal.strategy_name,
            finding_count=len(findings),
            findings=findings,
            evidence_summary=self._evidence_summary(risk_context, knowledge_context, memory_context),
        )

    @staticmethod
    def _overall_status(findings: List[AuditFinding]) -> str:
        if any(finding.severity == "high" for finding in findings):
            return "attention_required"
        if any(finding.severity == "medium" for finding in findings):
            return "review_recommended"
        return "passed"

    @staticmethod
    def _evidence_summary(
        risk_context: Dict[str, Any],
        knowledge_context: List[KnowledgeSnippet],
        memory_context: List[MemoryCase],
    ) -> Dict[str, Any]:
        context_evidence = risk_context.get("context_evidence", {})
        return {
            "risk_level": risk_context.get("risk_level", "unknown"),
            "risk_score": risk_context.get("risk_score", 0.0),
            "knowledge_count": len(knowledge_context),
            "memory_count": len(memory_context),
            "context_adjustment": context_evidence.get("context_adjustment", 0.0),
            "context_signals": list(context_evidence.get("signals", [])),
        }


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
