from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from models import StrategyProposal
from rag import KnowledgeSnippet


@dataclass(frozen=True)
class GroundingEvidence:
    evidence_id: str
    title: str
    source: str
    score: float
    content_excerpt: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "title": self.title,
            "source": self.source,
            "score": round(self.score, 4),
            "content_excerpt": self.content_excerpt,
        }


@dataclass(frozen=True)
class ProposalGrounding:
    agent_name: str
    strategy_name: str
    grounded: bool
    evidence: List[GroundingEvidence]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "strategy_name": self.strategy_name,
            "grounded": self.grounded,
            "evidence": [item.to_dict() for item in self.evidence],
            "evidence_titles": [item.title for item in self.evidence],
        }


@dataclass(frozen=True)
class RiskGrounding:
    risk_level: str
    evidence: List[GroundingEvidence]
    recommendation_grounding: List[Dict[str, Any]]
    signals: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_level": self.risk_level,
            "evidence": [item.to_dict() for item in self.evidence],
            "evidence_titles": [item.title for item in self.evidence],
            "recommendation_grounding": self.recommendation_grounding,
            "signals": self.signals,
        }


@dataclass(frozen=True)
class GroundingReport:
    status: str
    knowledge_evidence: List[GroundingEvidence]
    proposal_grounding: List[ProposalGrounding]
    risk_grounding: RiskGrounding

    def to_dict(self) -> Dict[str, Any]:
        grounded_proposals = sum(1 for item in self.proposal_grounding if item.grounded)
        risk_evidence_count = len(self.risk_grounding.evidence)
        return {
            "status": self.status,
            "knowledge_evidence": [item.to_dict() for item in self.knowledge_evidence],
            "proposal_grounding": [item.to_dict() for item in self.proposal_grounding],
            "risk_grounding": self.risk_grounding.to_dict(),
            "summary": {
                "knowledge_snippet_count": len(self.knowledge_evidence),
                "grounded_proposal_count": grounded_proposals,
                "ungrounded_proposal_count": len(self.proposal_grounding) - grounded_proposals,
                "risk_evidence_count": risk_evidence_count,
            },
        }


class GroundingBuilder:
    def build(
        self,
        *,
        knowledge_context: List[KnowledgeSnippet],
        proposals: List[StrategyProposal],
        risk_context: Dict[str, Any],
    ) -> GroundingReport:
        evidence = [
            GroundingEvidence(
                evidence_id=f"rag-{index}",
                title=snippet.title,
                source=snippet.source,
                score=snippet.score,
                content_excerpt=_excerpt(snippet.content),
            )
            for index, snippet in enumerate(knowledge_context, start=1)
        ]
        evidence_by_title = {item.title: item for item in evidence}
        proposal_grounding = [
            self._proposal_grounding(proposal, evidence_by_title)
            for proposal in proposals
        ]
        risk_grounding = self._risk_grounding(risk_context, evidence_by_title)
        status = "grounded" if evidence and (risk_grounding.evidence or any(item.grounded for item in proposal_grounding)) else "no_evidence"
        return GroundingReport(
            status=status,
            knowledge_evidence=evidence,
            proposal_grounding=proposal_grounding,
            risk_grounding=risk_grounding,
        )

    @staticmethod
    def _proposal_grounding(
        proposal: StrategyProposal,
        evidence_by_title: Dict[str, GroundingEvidence],
    ) -> ProposalGrounding:
        evidence = [
            evidence_by_title[title]
            for title in proposal.knowledge_sources
            if title in evidence_by_title
        ]
        return ProposalGrounding(
            agent_name=proposal.agent_name,
            strategy_name=proposal.strategy_name,
            grounded=bool(evidence),
            evidence=evidence,
        )

    @staticmethod
    def _risk_grounding(
        risk_context: Dict[str, Any],
        evidence_by_title: Dict[str, GroundingEvidence],
    ) -> RiskGrounding:
        context_evidence = risk_context.get("context_evidence", {})
        titles = context_evidence.get("knowledge_titles", [])
        evidence = [
            evidence_by_title[str(title)]
            for title in titles
            if str(title) in evidence_by_title
        ]
        evidence_ids = [item.evidence_id for item in evidence]
        recommendation_grounding = [
            {
                "recommendation": str(recommendation),
                "evidence_ids": evidence_ids,
                "evidence_titles": [item.title for item in evidence],
            }
            for recommendation in risk_context.get("recommendations", [])
        ]
        return RiskGrounding(
            risk_level=str(risk_context.get("risk_level", "unknown")),
            evidence=evidence,
            recommendation_grounding=recommendation_grounding,
            signals=[str(item) for item in context_evidence.get("signals", [])],
        )


def _excerpt(content: str, limit: int = 180) -> str:
    cleaned = " ".join(str(content).split())
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 3]}..."
