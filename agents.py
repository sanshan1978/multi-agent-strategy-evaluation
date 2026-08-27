from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from models import BattlefieldScene, StrategyProposal, clamp


def terrain_factor(terrain: str, mapping: Dict[str, float], default: float = 0.0) -> float:
    return mapping.get(terrain.lower(), default)


@dataclass
class BaseAgent:
    name: str
    strategy_name: str

    def propose(self, scene: BattlefieldScene) -> StrategyProposal:
        raise NotImplementedError


class AssaultAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(name="强攻智能体", strategy_name="快速正面突破")

    def propose(self, scene: BattlefieldScene) -> StrategyProposal:
        delta = scene.own_strength - scene.enemy_strength
        terrain_penalty = terrain_factor(scene.terrain, {"urban": 10, "mountain": 12, "forest": 6}, 4)
        success = 55 + 0.7 * delta + 0.25 * scene.urgency - terrain_penalty
        resource_eff = 45 + 0.2 * scene.supply_level - 0.1 * scene.urgency
        risk_control = 40 + 0.3 * scene.own_strength - 0.4 * scene.civilian_presence
        response_speed = 80 + 0.15 * scene.urgency
        intel_alignment = 50 + 0.3 * scene.intel_quality
        confidence = clamp(0.55 + 0.004 * delta + 0.002 * scene.urgency, 0.3, 0.95)
        return StrategyProposal(
            agent_name=self.name,
            strategy_name=self.strategy_name,
            summary="集中主力正面压制，力争在短时间内完成目标区域控制。",
            actions=[
                "组织主突击群，分批次推进至核心目标点。",
                "前沿火力持续压制敌方据点，限制敌机动。",
                "预备队在突破后快速接替，稳固占领区。",
            ],
            metric_scores={
                "success_prob": success,
                "resource_efficiency": resource_eff,
                "risk_control": risk_control,
                "response_speed": response_speed,
                "intel_alignment": intel_alignment,
            },
            rationale="在我方兵力占优或时间压力较大时，正面突击可快速形成战果。",
            confidence=confidence,
        )


class FlankAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(name="迂回智能体", strategy_name="侧翼穿插包抄")

    def propose(self, scene: BattlefieldScene) -> StrategyProposal:
        terrain_bonus = terrain_factor(scene.terrain, {"forest": 12, "plain": 10, "urban": -2, "mountain": 4}, 5)
        success = 50 + 0.45 * (scene.own_strength - scene.enemy_strength) + 0.35 * scene.intel_quality + terrain_bonus
        resource_eff = 60 + 0.2 * scene.supply_level - 0.1 * scene.urgency
        risk_control = 55 + 0.25 * scene.intel_quality - 0.2 * scene.civilian_presence
        response_speed = 58 + 0.2 * scene.urgency + terrain_bonus * 0.2
        intel_alignment = 62 + 0.35 * scene.intel_quality
        confidence = clamp(0.60 + 0.003 * scene.intel_quality + terrain_bonus / 200.0, 0.35, 0.95)
        return StrategyProposal(
            agent_name=self.name,
            strategy_name=self.strategy_name,
            summary="以佯攻吸引敌主力，主力从侧翼隐蔽突入形成局部包围。",
            actions=[
                "正面分队实施牵制性火力，制造主攻假象。",
                "侧翼机动群利用地形接近敌薄弱区域。",
                "在敌指挥链暴露后快速切断补给与撤退通道。",
            ],
            metric_scores={
                "success_prob": success,
                "resource_efficiency": resource_eff,
                "risk_control": risk_control,
                "response_speed": response_speed,
                "intel_alignment": intel_alignment,
            },
            rationale="依赖情报和机动能力，通过局部优势降低正面消耗。",
            confidence=confidence,
        )


class DefenseAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(name="防御智能体", strategy_name="弹性防御反击")

    def propose(self, scene: BattlefieldScene) -> StrategyProposal:
        enemy_pressure = scene.enemy_strength - scene.own_strength
        success = 52 + 0.4 * max(enemy_pressure, 0) + 0.2 * scene.supply_level + 0.2 * scene.intel_quality
        resource_eff = 68 + 0.2 * scene.supply_level
        risk_control = 72 + 0.15 * scene.civilian_presence + 0.2 * scene.intel_quality
        response_speed = 45 + 0.1 * scene.urgency
        intel_alignment = 58 + 0.25 * scene.intel_quality
        confidence = clamp(0.58 + 0.002 * scene.enemy_strength + 0.002 * scene.civilian_presence, 0.35, 0.95)
        return StrategyProposal(
            agent_name=self.name,
            strategy_name=self.strategy_name,
            summary="先稳固关键节点，诱敌深入后在有利地段实施反击。",
            actions=[
                "构建纵深防御，优先保护指挥通信与补给线。",
                "机动预备队在敌突进后实施局部反冲击。",
                "根据敌损耗情况决定转入追击或持续防守。",
            ],
            metric_scores={
                "success_prob": success,
                "resource_efficiency": resource_eff,
                "risk_control": risk_control,
                "response_speed": response_speed,
                "intel_alignment": intel_alignment,
            },
            rationale="在敌强我弱或平民密集场景中，先控风险再反击更稳妥。",
            confidence=confidence,
        )


class DeceptionAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(name="诱骗智能体", strategy_name="欺骗诱导分割")

    def propose(self, scene: BattlefieldScene) -> StrategyProposal:
        intel_bonus = 0.5 * scene.intel_quality
        success = 46 + intel_bonus + 0.15 * (scene.own_strength - scene.enemy_strength)
        resource_eff = 64 + 0.1 * scene.supply_level + 0.2 * scene.intel_quality
        risk_control = 63 + 0.18 * scene.intel_quality - 0.18 * scene.civilian_presence
        response_speed = 52 + 0.12 * scene.urgency
        intel_alignment = 70 + 0.22 * scene.intel_quality
        confidence = clamp(0.57 + 0.004 * scene.intel_quality - 0.001 * scene.weather.lower().count("storm"), 0.35, 0.95)
        return StrategyProposal(
            agent_name=self.name,
            strategy_name=self.strategy_name,
            summary="通过电子欺骗和战术佯动误导敌指挥，促使敌部署失衡。",
            actions=[
                "制造多个假目标信号，迫使敌分散侦察资源。",
                "利用诱饵分队牵引敌机动，暴露其真实火力配置。",
                "在敌阵型分离后联合主力实施定点打击。",
            ],
            metric_scores={
                "success_prob": success,
                "resource_efficiency": resource_eff,
                "risk_control": risk_control,
                "response_speed": response_speed,
                "intel_alignment": intel_alignment,
            },
            rationale="重情报与认知优势，适合破坏敌决策节奏。",
            confidence=confidence,
        )


class FireSupportAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(name="火力压制智能体", strategy_name="远程火力削弱后突入")

    def propose(self, scene: BattlefieldScene) -> StrategyProposal:
        supply_bonus = 0.45 * scene.supply_level
        success = 50 + supply_bonus * 0.5 + 0.25 * scene.intel_quality - 0.1 * scene.civilian_presence
        resource_eff = 48 + 0.35 * scene.supply_level
        risk_control = 55 + 0.25 * scene.intel_quality - 0.25 * scene.civilian_presence
        response_speed = 60 + 0.1 * scene.urgency
        intel_alignment = 60 + 0.3 * scene.intel_quality
        confidence = clamp(0.59 + 0.003 * scene.supply_level + 0.002 * scene.intel_quality, 0.35, 0.95)
        return StrategyProposal(
            agent_name=self.name,
            strategy_name=self.strategy_name,
            summary="优先使用远程火力压制关键节点，再组织突入减少接触损失。",
            actions=[
                "联合侦察定位敌指挥、火力与补给节点。",
                "实施分时段火力覆盖，限制敌反制能力。",
                "火力窗口期内机动部队快速夺占关键点。",
            ],
            metric_scores={
                "success_prob": success,
                "resource_efficiency": resource_eff,
                "risk_control": risk_control,
                "response_speed": response_speed,
                "intel_alignment": intel_alignment,
            },
            rationale="在补给和情报条件较好时，可有效降低正面突击风险。",
            confidence=confidence,
        )


def build_default_agents() -> List[BaseAgent]:
    return [
        AssaultAgent(),
        FlankAgent(),
        DefenseAgent(),
        DeceptionAgent(),
        FireSupportAgent(),
    ]
