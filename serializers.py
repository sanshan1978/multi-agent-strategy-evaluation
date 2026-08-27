from __future__ import annotations

from typing import Any, Dict

from models import BattlefieldScene, DebateMessage, ScoredProposal, StrategyProposal
from trace import TraceEvent


def scene_to_dict(scene: BattlefieldScene) -> Dict[str, Any]:
    return {
        "name": scene.name,
        "objective": scene.objective,
        "terrain": scene.terrain,
        "weather": scene.weather,
        "enemy_strength": scene.enemy_strength,
        "own_strength": scene.own_strength,
        "supply_level": scene.supply_level,
        "intel_quality": scene.intel_quality,
        "urgency": scene.urgency,
        "civilian_presence": scene.civilian_presence,
    }


def proposal_to_dict(proposal: StrategyProposal) -> Dict[str, Any]:
    return {
        "agent_name": proposal.agent_name,
        "strategy_name": proposal.strategy_name,
        "summary": proposal.summary,
        "actions": proposal.actions,
        "metric_scores": proposal.normalized_metric_scores(),
        "rationale": proposal.rationale,
        "confidence": proposal.confidence,
        "peer_support": proposal.peer_support,
        "knowledge_sources": proposal.knowledge_sources,
        "memory_sources": proposal.memory_sources,
    }


def scored_to_dict(item: ScoredProposal) -> Dict[str, Any]:
    return {
        "proposal": proposal_to_dict(item.proposal),
        "weightedScore": item.weighted_score,
        "finalScore": item.final_score,
        "llmBonus": item.llm_bonus,
    }


def message_to_dict(message: DebateMessage) -> Dict[str, Any]:
    return {
        "from_agent": message.from_agent,
        "to_agent": message.to_agent,
        "content": message.content,
        "impact": message.impact,
    }


def trace_to_dict(event: TraceEvent) -> Dict[str, Any]:
    return {
        "step": event.step,
        "message": event.message,
        "status": event.status,
        "metadata": event.metadata,
        "timestamp": event.timestamp,
    }


def result_to_dict(result: Any) -> Dict[str, Any]:
    return {
        "best": scored_to_dict(result.best),
        "ranking": [scored_to_dict(item) for item in result.ranking],
        "messages": [message_to_dict(message) for message in result.messages],
        "weights": result.weights,
        "decision_mode": result.decision_mode,
        "knowledge_context": [item.to_dict() for item in result.knowledge_context],
        "memory_context": [item.to_dict() for item in result.memory_context],
        "risk_context": result.risk_context,
        "grounding_evidence": result.grounding_evidence,
        "tool_plan": result.tool_plan.to_dict(),
        "tool_calls": [item.to_dict() for item in result.tool_calls],
        "tool_metrics": result.tool_metrics,
        "plan_execution_audit": result.plan_execution_audit,
        "workflow_nodes": result.workflow_nodes,
        "decision_audit": result.decision_audit,
        "trace": [trace_to_dict(event) for event in result.trace],
        "llm_recommended_agent": result.llm_recommended_agent,
        "llm_reason": result.llm_reason,
        "llm_error": result.llm_error,
        "agent_generation": [record.to_dict() for record in result.agent_generation_records],
    }
