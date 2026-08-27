from __future__ import annotations

import time
from typing import Any, Dict, List

from memory import MemoryCase
from models import BattlefieldScene
from rag import KnowledgeSnippet
from tools.base import ToolResult, ToolSpec, measured_tool_result


class RiskAnalysisTool:
    name = "risk_analysis"

    def run(
        self,
        scene: BattlefieldScene,
        knowledge_context: List[KnowledgeSnippet] | None = None,
        memory_context: List[MemoryCase] | None = None,
    ) -> ToolResult:
        started_at = time.perf_counter()
        output = analyze_scene_risk(
            scene,
            knowledge_context=knowledge_context or [],
            memory_context=memory_context or [],
        )
        context_evidence = output.get("context_evidence", {})
        return measured_tool_result(
            tool_name=self.name,
            started_at=started_at,
            output=output,
            metadata={
                "risk_level": output["risk_level"],
                "risk_score": output["risk_score"],
                "factor_count": len(output["factors"]),
                "knowledge_evidence_count": len(context_evidence.get("knowledge_titles", [])),
                "memory_evidence_count": len(context_evidence.get("memory_case_ids", [])),
            },
        )

    def describe(self) -> ToolSpec:
        return ToolSpec(
            name=self.name,
            description="Analyze battlefield risk level from scene pressure, civilians, intel, supply and terrain.",
            input_schema={
                "type": "object",
                "required": ["scene"],
                "properties": {
                    "scene": {"type": "BattlefieldScene"},
                    "knowledge_context": {
                        "type": "array",
                        "items": {"type": "KnowledgeSnippet"},
                        "description": "Optional RAG snippets produced by knowledge_retrieval.",
                    },
                    "memory_context": {
                        "type": "array",
                        "items": {"type": "MemoryCase"},
                        "description": "Optional historical cases produced by memory_recall.",
                    },
                },
            },
            output_schema={
                "type": "object",
                "properties": {
                    "risk_score": {"type": "number"},
                    "risk_level": {"type": "string", "enum": ["low", "medium", "high", "unknown"]},
                    "factors": {"type": "array", "items": {"type": "string"}},
                    "recommendations": {"type": "array", "items": {"type": "string"}},
                    "context_evidence": {
                        "type": "object",
                        "description": "Knowledge and memory evidence used to adjust risk analysis.",
                    },
                },
            },
            tags=["risk", "rule_based", "analysis", "context_aware"],
        )


def analyze_scene_risk(
    scene: BattlefieldScene,
    knowledge_context: List[KnowledgeSnippet] | None = None,
    memory_context: List[MemoryCase] | None = None,
) -> Dict[str, Any]:
    factors: List[str] = []
    score = 0.0

    enemy_pressure = max(0, scene.enemy_strength - scene.own_strength)
    score += enemy_pressure * 0.22
    if enemy_pressure >= 10:
        factors.append("enemy_pressure")

    score += scene.civilian_presence * 0.24
    if scene.civilian_presence >= 70:
        factors.append("civilian_dense")

    score += scene.urgency * 0.16
    if scene.urgency >= 80:
        factors.append("high_urgency")

    low_intel = max(0, 70 - scene.intel_quality)
    score += low_intel * 0.18
    if scene.intel_quality < 60:
        factors.append("low_intel")

    low_supply = max(0, 65 - scene.supply_level)
    score += low_supply * 0.12
    if scene.supply_level < 60:
        factors.append("low_supply")

    terrain_risk = {
        "urban": 8,
        "mountain": 7,
        "forest": 5,
        "plain": 3,
    }.get(scene.terrain.lower(), 4)
    score += terrain_risk
    if terrain_risk >= 7:
        factors.append(f"{scene.terrain.lower()}_terrain")

    context_evidence = _build_context_evidence(
        scene,
        knowledge_context or [],
        memory_context or [],
        factors,
    )
    score += float(context_evidence["context_adjustment"])

    risk_score = round(min(score, 100.0), 2)
    if risk_score >= 65:
        risk_level = "high"
    elif risk_score >= 40:
        risk_level = "medium"
    else:
        risk_level = "low"

    recommendations = _risk_recommendations(factors, risk_level)
    recommendations.extend(context_evidence["recommendations"])
    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "factors": factors,
        "recommendations": recommendations,
        "context_evidence": context_evidence,
    }


def _build_context_evidence(
    scene: BattlefieldScene,
    knowledge_context: List[KnowledgeSnippet],
    memory_context: List[MemoryCase],
    factors: List[str],
) -> Dict[str, Any]:
    signals: List[str] = []
    recommendations: List[str] = []
    adjustment = 0.0

    for snippet in knowledge_context[:5]:
        text = f"{snippet.title} {snippet.content}".lower()
        if scene.civilian_presence >= 60 and any(token in text for token in ["civilian", "civilian_dense", "collateral"]):
            adjustment += 3.5
            _append_once(factors, "knowledge_civilian_risk")
            _append_once(signals, "knowledge_civilian_risk")
        if scene.intel_quality < 70 and any(token in text for token in ["low_intel", "reconnaissance"]):
            adjustment += 2.5
            _append_once(factors, "knowledge_intel_gap")
            _append_once(signals, "knowledge_intel_gap")
        if scene.supply_level < 65 and "low_supply" in text:
            adjustment += 2.0
            _append_once(factors, "knowledge_supply_risk")
            _append_once(signals, "knowledge_supply_risk")
        if scene.urgency >= 75 and any(token in text for token in ["high_urgency", "rapid_response"]):
            adjustment += 2.0
            _append_once(factors, "knowledge_urgency_risk")
            _append_once(signals, "knowledge_urgency_risk")
        if scene.enemy_strength >= scene.own_strength and any(token in text for token in ["enemy_stronger", "defense"]):
            adjustment += 3.0
            _append_once(factors, "knowledge_enemy_pressure")
            _append_once(signals, "knowledge_enemy_pressure")

    high_similarity_cases = [case for case in memory_context[:5] if case.similarity >= 0.7]
    if high_similarity_cases:
        adjustment += min(6.0, 2.0 + len(high_similarity_cases) * 1.5)
        _append_once(factors, "memory_similar_case_pressure")
        _append_once(signals, "memory_similar_case_pressure")
        recommendations.append("参考高相似历史案例，复核当前方案是否存在重复风险与执行盲区")

    if signals and knowledge_context:
        recommendations.append("结合 RAG 知识证据补充风险约束，避免只依赖场景数值判断")

    return {
        "knowledge_titles": [item.title for item in knowledge_context[:5]],
        "memory_case_ids": [item.record_id for item in memory_context[:5]],
        "signals": signals,
        "context_adjustment": round(min(adjustment, 12.0), 2),
        "recommendations": recommendations,
    }


def _append_once(items: List[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _risk_recommendations(factors: List[str], risk_level: str) -> List[str]:
    recommendations: List[str] = []
    if "civilian_dense" in factors:
        recommendations.append("优先控制附带损害，保留疏散与通信保障通道")
    if "low_intel" in factors:
        recommendations.append("先补充侦察和诱导试探，降低盲目突击风险")
    if "enemy_pressure" in factors:
        recommendations.append("避免单点正面硬碰，使用纵深防御或侧翼牵制")
    if "high_urgency" in factors:
        recommendations.append("缩短指挥链路，采用阶段化快速反馈方案")
    if not recommendations and risk_level == "low":
        recommendations.append("可优先选择机动和效率较高的方案")
    return recommendations
