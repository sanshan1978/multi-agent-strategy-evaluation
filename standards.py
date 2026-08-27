from __future__ import annotations

from typing import Dict, List

from models import BattlefieldScene, StrategyProposal, clamp


METRICS: List[str] = [
    "success_prob",
    "resource_efficiency",
    "risk_control",
    "response_speed",
    "intel_alignment",
]


def build_dynamic_weights(scene: BattlefieldScene) -> Dict[str, float]:
    weights = {
        "success_prob": 0.28,
        "resource_efficiency": 0.18,
        "risk_control": 0.20,
        "response_speed": 0.18,
        "intel_alignment": 0.16,
    }

    if scene.urgency >= 70:
        weights["response_speed"] += 0.08
        weights["success_prob"] += 0.03
        weights["resource_efficiency"] -= 0.04

    if scene.civilian_presence >= 60:
        weights["risk_control"] += 0.10
        weights["success_prob"] -= 0.03
        weights["response_speed"] -= 0.02

    if scene.supply_level <= 40:
        weights["resource_efficiency"] += 0.08
        weights["response_speed"] -= 0.02

    if scene.intel_quality <= 40:
        weights["intel_alignment"] += 0.06
        weights["success_prob"] -= 0.02
    elif scene.intel_quality >= 75:
        weights["intel_alignment"] += 0.04
        weights["success_prob"] += 0.02

    total = sum(max(v, 0.01) for v in weights.values())
    return {k: max(v, 0.01) / total for k, v in weights.items()}


def evaluate_weighted_score(proposal: StrategyProposal, weights: Dict[str, float]) -> float:
    normalized_scores = proposal.normalized_metric_scores()
    score = 0.0
    for metric, weight in weights.items():
        score += normalized_scores.get(metric, 0.0) * weight
    return clamp(score, 0.0, 100.0)


def priority_metrics(scene: BattlefieldScene) -> List[str]:
    ordered = []
    if scene.civilian_presence >= 60:
        ordered.append("risk_control")
    if scene.urgency >= 70:
        ordered.append("response_speed")
    if scene.supply_level <= 40:
        ordered.append("resource_efficiency")
    if scene.intel_quality <= 45 or scene.intel_quality >= 75:
        ordered.append("intel_alignment")
    ordered.append("success_prob")
    return ordered

