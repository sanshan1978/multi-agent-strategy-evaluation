from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


@dataclass
class BattlefieldScene:
    name: str
    objective: str
    terrain: str
    weather: str
    enemy_strength: int  # 0-100
    own_strength: int  # 0-100
    supply_level: int  # 0-100
    intel_quality: int  # 0-100
    urgency: int  # 0-100
    civilian_presence: int  # 0-100

    def strength_ratio(self) -> float:
        return self.own_strength / max(self.enemy_strength, 1)


@dataclass(frozen=True)
class AgentGenerationRecord:
    agent_name: str
    strategy_name: str
    generation_mode: str
    model: str | None = None
    duration_ms: float = 0.0
    validation_status: str = "not_applicable"
    fallback_reason: str | None = None
    knowledge_sources: List[str] = field(default_factory=list)
    memory_sources: List[int] = field(default_factory=list)
    metric_adjustments: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "agent_name": self.agent_name,
            "strategy_name": self.strategy_name,
            "generation_mode": self.generation_mode,
            "model": self.model,
            "duration_ms": round(self.duration_ms, 3),
            "validation_status": self.validation_status,
            "fallback_reason": self.fallback_reason,
            "knowledge_sources": list(self.knowledge_sources),
            "memory_sources": list(self.memory_sources),
            "metric_adjustments": dict(self.metric_adjustments),
        }


@dataclass
class StrategyProposal:
    agent_name: str
    strategy_name: str
    summary: str
    actions: List[str]
    metric_scores: Dict[str, float]  # success_prob, resource_efficiency, risk_control, response_speed, intel_alignment
    rationale: str
    confidence: float = 0.6  # 0-1
    peer_support: float = 0.0
    knowledge_sources: List[str] = field(default_factory=list)
    memory_sources: List[int] = field(default_factory=list)

    def normalized_metric_scores(self) -> Dict[str, float]:
        return {k: clamp(v) for k, v in self.metric_scores.items()}


@dataclass
class DebateMessage:
    from_agent: str
    to_agent: str
    content: str
    impact: float  # -0.2 ~ 0.2


@dataclass
class ScoredProposal:
    proposal: StrategyProposal
    weighted_score: float
    final_score: float
    llm_bonus: float = 0.0
    weights: Dict[str, float] = field(default_factory=dict)
