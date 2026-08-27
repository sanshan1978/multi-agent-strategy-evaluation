from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence

from models import BattlefieldScene


@dataclass(frozen=True)
class ToolPlanStep:
    sequence: int
    tool_name: str
    purpose: str
    parameters: Dict[str, Any]
    required: bool = True
    need_score: float = 0.0
    threshold: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sequence": self.sequence,
            "tool_name": self.tool_name,
            "purpose": self.purpose,
            "parameters": self.parameters,
            "required": self.required,
            "need_score": round(self.need_score, 2),
            "threshold": round(self.threshold, 2),
        }


@dataclass(frozen=True)
class SkippedToolStep:
    tool_name: str
    reason: str
    condition: str
    need_score: float = 0.0
    threshold: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "reason": self.reason,
            "condition": self.condition,
            "need_score": round(self.need_score, 2),
            "threshold": round(self.threshold, 2),
        }


@dataclass(frozen=True)
class PlanValidationIssue:
    code: str
    severity: str
    message: str
    tool_name: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "tool_name": self.tool_name,
        }


@dataclass(frozen=True)
class PlanRepairAction:
    action: str
    reason: str
    tool_name: str | None = None
    before: Any | None = None
    after: Any | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
            "tool_name": self.tool_name,
            "before": self.before,
            "after": self.after,
        }


@dataclass(frozen=True)
class PlanValidationReport:
    status: str
    issues: List[PlanValidationIssue]
    repair_actions: List[PlanRepairAction]
    original_tool_order: List[str]
    repaired_tool_order: List[str]
    available_tools: List[str]

    @property
    def repair_count(self) -> int:
        return len(self.repair_actions)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "issues": [issue.to_dict() for issue in self.issues],
            "repair_actions": [action.to_dict() for action in self.repair_actions],
            "repair_count": self.repair_count,
            "original_tool_order": self.original_tool_order,
            "repaired_tool_order": self.repaired_tool_order,
            "available_tools": self.available_tools,
        }


@dataclass(frozen=True)
class AgentToolPlan:
    objective: str
    strategy: str
    steps: List[ToolPlanStep]
    skipped_steps: List[SkippedToolStep]
    planner_source: str = "rule-based"
    planner_model: str | None = None
    planner_error: str | None = None
    validation_status: str = "not_checked"
    validation_issues: List[Dict[str, Any]] = field(default_factory=list)
    repair_actions: List[Dict[str, Any]] = field(default_factory=list)

    def step_for(self, tool_name: str) -> ToolPlanStep:
        for step in self.steps:
            if step.tool_name == tool_name:
                return step
        raise KeyError(f"Tool is not in current plan: {tool_name}")

    def optional_step_for(self, tool_name: str) -> ToolPlanStep | None:
        for step in self.steps:
            if step.tool_name == tool_name:
                return step
        return None

    def skipped_step_for(self, tool_name: str) -> SkippedToolStep | None:
        for step in self.skipped_steps:
            if step.tool_name == tool_name:
                return step
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "objective": self.objective,
            "strategy": self.strategy,
            "steps": [step.to_dict() for step in self.steps],
            "skipped_steps": [step.to_dict() for step in self.skipped_steps],
            "planner_source": self.planner_source,
            "planner_model": self.planner_model,
            "planner_error": self.planner_error,
            "validation_status": self.validation_status,
            "validation_issues": self.validation_issues,
            "repair_actions": self.repair_actions,
        }

    def with_planner_metadata(
        self,
        planner_source: str,
        planner_model: str | None = None,
        planner_error: str | None = None,
    ) -> "AgentToolPlan":
        return AgentToolPlan(
            objective=self.objective,
            strategy=self.strategy,
            steps=self.steps,
            skipped_steps=self.skipped_steps,
            planner_source=planner_source,
            planner_model=planner_model,
            planner_error=planner_error,
            validation_status=self.validation_status,
            validation_issues=self.validation_issues,
            repair_actions=self.repair_actions,
        )

    def with_validation_report(self, report: PlanValidationReport) -> "AgentToolPlan":
        return AgentToolPlan(
            objective=self.objective,
            strategy=self.strategy,
            steps=self.steps,
            skipped_steps=self.skipped_steps,
            planner_source=self.planner_source,
            planner_model=self.planner_model,
            planner_error=self.planner_error,
            validation_status=report.status,
            validation_issues=[issue.to_dict() for issue in report.issues],
            repair_actions=[action.to_dict() for action in report.repair_actions],
        )


class PlanValidator:
    canonical_order = ["knowledge_retrieval", "memory_recall", "risk_analysis"]

    def validate_and_repair(
        self,
        plan: AgentToolPlan,
        *,
        fallback_plan: AgentToolPlan,
        available_tools: Sequence[str],
    ) -> tuple[AgentToolPlan, PlanValidationReport]:
        available = [tool for tool in available_tools if str(tool).strip()]
        available_set = set(available)
        original_order = [step.tool_name for step in plan.steps]
        fallback_steps = {step.tool_name: step for step in fallback_plan.steps}
        fallback_skips = {step.tool_name: step for step in fallback_plan.skipped_steps}
        issues: List[PlanValidationIssue] = []
        repairs: List[PlanRepairAction] = []
        cleaned_steps: List[ToolPlanStep] = []
        seen: set[str] = set()

        for step in plan.steps:
            if step.tool_name not in available_set:
                issues.append(
                    PlanValidationIssue(
                        code="unknown_tool",
                        severity="error",
                        message=f"tool is not available: {step.tool_name}",
                        tool_name=step.tool_name,
                    )
                )
                repairs.append(
                    PlanRepairAction(
                        action="remove_unknown_tool",
                        reason="tool is not registered in available tool registry",
                        tool_name=step.tool_name,
                        before=step.to_dict(),
                    )
                )
                continue
            if step.tool_name in seen:
                issues.append(
                    PlanValidationIssue(
                        code="duplicate_tool",
                        severity="warning",
                        message=f"duplicate tool step removed: {step.tool_name}",
                        tool_name=step.tool_name,
                    )
                )
                repairs.append(
                    PlanRepairAction(
                        action="remove_duplicate_tool",
                        reason="a tool should be executed at most once in the current DAG",
                        tool_name=step.tool_name,
                        before=step.to_dict(),
                    )
                )
                continue

            sanitized_parameters = self._sanitize_parameters(step.tool_name, step.parameters)
            if sanitized_parameters != step.parameters:
                issues.append(
                    PlanValidationIssue(
                        code="invalid_parameters",
                        severity="warning",
                        message=f"parameters sanitized for {step.tool_name}",
                        tool_name=step.tool_name,
                    )
                )
                repairs.append(
                    PlanRepairAction(
                        action="sanitize_parameters",
                        reason="tool parameters must match local tool schema limits",
                        tool_name=step.tool_name,
                        before=step.parameters,
                        after=sanitized_parameters,
                    )
                )
            score_reference = fallback_steps.get(step.tool_name) or fallback_skips.get(step.tool_name)
            cleaned_steps.append(
                ToolPlanStep(
                    sequence=step.sequence,
                    tool_name=step.tool_name,
                    purpose=step.purpose,
                    parameters=sanitized_parameters,
                    required=step.required,
                    need_score=score_reference.need_score if score_reference else step.need_score,
                    threshold=score_reference.threshold if score_reference else step.threshold,
                )
            )
            seen.add(step.tool_name)

        for fallback_step in fallback_plan.steps:
            if fallback_step.tool_name not in available_set or fallback_step.tool_name in seen:
                continue
            issues.append(
                PlanValidationIssue(
                    code="missing_required_tool",
                    severity="warning",
                    message=f"fallback planner marked tool as needed: {fallback_step.tool_name}",
                    tool_name=fallback_step.tool_name,
                )
            )
            repairs.append(
                PlanRepairAction(
                    action="add_missing_required_tool",
                    reason="fallback plan selected this tool above threshold",
                    tool_name=fallback_step.tool_name,
                    after=fallback_step.to_dict(),
                )
            )
            cleaned_steps.append(fallback_step)
            seen.add(fallback_step.tool_name)

        ordered_steps = self._order_steps(cleaned_steps, available)
        order_changed = [step.tool_name for step in ordered_steps] != [step.tool_name for step in cleaned_steps]
        sequence_changed = [step.sequence for step in ordered_steps] != list(range(1, len(ordered_steps) + 1))
        if order_changed or sequence_changed:
            issues.append(
                PlanValidationIssue(
                    code="step_order_repaired",
                    severity="warning",
                    message="tool steps were reordered into dependency-safe execution order",
                )
            )
            repairs.append(
                PlanRepairAction(
                    action="reorder_steps",
                    reason="tool DAG requires knowledge and memory before risk analysis",
                    before=[step.to_dict() for step in cleaned_steps],
                    after=[step.tool_name for step in ordered_steps],
                )
            )

        repaired_steps = [
            ToolPlanStep(
                sequence=index,
                tool_name=step.tool_name,
                purpose=step.purpose,
                parameters=step.parameters,
                required=step.required,
                need_score=step.need_score,
                threshold=step.threshold,
            )
            for index, step in enumerate(ordered_steps, start=1)
        ]
        selected = {step.tool_name for step in repaired_steps}
        repaired_skips = self._repair_skipped_steps(
            plan=plan,
            fallback_plan=fallback_plan,
            available_tools=available,
            selected_tools=selected,
        )

        status = "valid"
        if repairs:
            status = "repaired"
        if not repaired_steps:
            status = "invalid"
            issues.append(
                PlanValidationIssue(
                    code="empty_plan",
                    severity="error",
                    message="plan has no executable tool steps after repair",
                )
            )

        repaired_plan = AgentToolPlan(
            objective=plan.objective,
            strategy=plan.strategy,
            steps=repaired_steps,
            skipped_steps=repaired_skips,
            planner_source=plan.planner_source,
            planner_model=plan.planner_model,
            planner_error=plan.planner_error,
        )
        report = PlanValidationReport(
            status=status,
            issues=issues,
            repair_actions=repairs,
            original_tool_order=original_order,
            repaired_tool_order=[step.tool_name for step in repaired_steps],
            available_tools=available,
        )
        return repaired_plan.with_validation_report(report), report

    @classmethod
    def _order_steps(cls, steps: List[ToolPlanStep], available_tools: Sequence[str]) -> List[ToolPlanStep]:
        fallback_order = {tool: index for index, tool in enumerate(available_tools, start=len(cls.canonical_order) + 1)}
        order = {
            tool: index
            for index, tool in enumerate(cls.canonical_order, start=1)
        }
        return sorted(
            steps,
            key=lambda step: (order.get(step.tool_name, fallback_order.get(step.tool_name, 999)), step.sequence),
        )

    @staticmethod
    def _sanitize_parameters(tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        raw_parameters = parameters if isinstance(parameters, dict) else {}
        if tool_name in {"knowledge_retrieval", "memory_recall"}:
            try:
                top_k = int(raw_parameters.get("top_k", 3))
            except (TypeError, ValueError):
                top_k = 3
            return {"top_k": max(1, min(top_k, 6))}
        return {}

    @staticmethod
    def _repair_skipped_steps(
        *,
        plan: AgentToolPlan,
        fallback_plan: AgentToolPlan,
        available_tools: Sequence[str],
        selected_tools: set[str],
    ) -> List[SkippedToolStep]:
        existing_skips = {step.tool_name: step for step in plan.skipped_steps}
        fallback_skips = {step.tool_name: step for step in fallback_plan.skipped_steps}
        fallback_steps = {step.tool_name: step for step in fallback_plan.steps}
        repaired: List[SkippedToolStep] = []
        for tool_name in available_tools:
            if tool_name in selected_tools:
                continue
            existing = existing_skips.get(tool_name)
            fallback_skip = fallback_skips.get(tool_name)
            score_reference = fallback_skip or fallback_steps.get(tool_name)
            if existing is not None:
                repaired.append(
                    SkippedToolStep(
                        tool_name=tool_name,
                        reason=existing.reason,
                        condition=existing.condition,
                        need_score=score_reference.need_score if score_reference else existing.need_score,
                        threshold=score_reference.threshold if score_reference else existing.threshold,
                    )
                )
                continue
            if fallback_skip is not None:
                repaired.append(fallback_skip)
                continue
            repaired.append(
                SkippedToolStep(
                    tool_name=tool_name,
                    reason="not_selected_after_plan_repair",
                    condition="tool not present in repaired plan",
                    need_score=score_reference.need_score if score_reference else 0.0,
                    threshold=score_reference.threshold if score_reference else 0.0,
                )
            )
        return repaired


class RuleBasedToolPlanner:
    def plan(self, scene: BattlefieldScene, available_tools: List[str]) -> AgentToolPlan:
        available = set(available_tools)
        steps: List[ToolPlanStep] = []
        skipped_steps: List[SkippedToolStep] = []
        sequence = 1

        if "knowledge_retrieval" in available:
            need_score = self._knowledge_need_score(scene)
            threshold = 35.0
            if need_score >= threshold:
                knowledge_top_k = 4 if scene.intel_quality < 60 or scene.civilian_presence >= 75 else 3
                steps.append(
                    ToolPlanStep(
                        sequence=sequence,
                        tool_name="knowledge_retrieval",
                        purpose="collect_scene_knowledge",
                        parameters={"top_k": knowledge_top_k},
                        need_score=need_score,
                        threshold=threshold,
                    )
                )
                sequence += 1
            else:
                skipped_steps.append(
                    SkippedToolStep(
                        tool_name="knowledge_retrieval",
                        reason="sufficient_intel_and_low_civilian_pressure",
                        condition="intel_quality>=70 and civilian_presence<70 and urgency<85",
                        need_score=need_score,
                        threshold=threshold,
                    )
                )

        if "memory_recall" in available:
            terrain = scene.terrain.lower()
            need_score = self._memory_need_score(scene)
            threshold = 35.0
            if need_score >= threshold:
                memory_top_k = 4 if terrain in {"urban", "mountain"} else 3
                steps.append(
                    ToolPlanStep(
                        sequence=sequence,
                        tool_name="memory_recall",
                        purpose="compare_similar_decisions",
                        parameters={"top_k": memory_top_k},
                        need_score=need_score,
                        threshold=threshold,
                    )
                )
                sequence += 1
            else:
                skipped_steps.append(
                    SkippedToolStep(
                        tool_name="memory_recall",
                        reason="no_complex_terrain_or_enemy_pressure",
                        condition="terrain not in {urban,mountain} and urgency<80 and enemy_strength<own_strength",
                        need_score=need_score,
                        threshold=threshold,
                    )
                )

        if "risk_analysis" in available:
            need_score = self._risk_need_score(scene)
            threshold = 10.0
            if need_score >= threshold:
                steps.append(
                    ToolPlanStep(
                        sequence=sequence,
                        tool_name="risk_analysis",
                        purpose="identify_operational_risk",
                        parameters={},
                        need_score=need_score,
                        threshold=threshold,
                    )
                )
            else:
                skipped_steps.append(
                    SkippedToolStep(
                        tool_name="risk_analysis",
                        reason="low_operational_risk_signal",
                        condition="civilian_presence<60 and urgency<70 and enemy_strength<own_strength and supply_level>=50",
                        need_score=need_score,
                        threshold=threshold,
                    )
                )

        return AgentToolPlan(
            objective=scene.objective,
            strategy=self._planning_strategy(scene),
            steps=steps,
            skipped_steps=skipped_steps,
        )

    @staticmethod
    def _knowledge_need_score(scene: BattlefieldScene) -> float:
        intel_gap = max(0, 70 - scene.intel_quality) * 1.1
        civilian_pressure = max(0, scene.civilian_presence - 50) * 0.6
        urgency_pressure = max(0, scene.urgency - 65) * 0.7
        return min(100.0, intel_gap + civilian_pressure + urgency_pressure)

    @staticmethod
    def _memory_need_score(scene: BattlefieldScene) -> float:
        terrain_bonus = 45.0 if scene.terrain.lower() in {"urban", "mountain"} else 0.0
        urgency_pressure = max(0, scene.urgency - 70) * 0.8
        enemy_pressure = max(0, scene.enemy_strength - scene.own_strength) * 1.2
        return min(100.0, terrain_bonus + urgency_pressure + enemy_pressure)

    @staticmethod
    def _risk_need_score(scene: BattlefieldScene) -> float:
        civilian_pressure = max(0, scene.civilian_presence - 40) * 0.7
        urgency_pressure = max(0, scene.urgency - 50) * 0.5
        enemy_pressure = max(0, scene.enemy_strength - scene.own_strength) * 1.3
        supply_pressure = max(0, 55 - scene.supply_level) * 0.8
        return min(100.0, civilian_pressure + urgency_pressure + enemy_pressure + supply_pressure)

    @staticmethod
    def _planning_strategy(scene: BattlefieldScene) -> str:
        tags: List[str] = []
        if scene.urgency >= 80:
            tags.append("time_sensitive")
        if scene.civilian_presence >= 70:
            tags.append("civilian_sensitive")
        if scene.intel_quality < 60:
            tags.append("intel_constrained")
        if scene.enemy_strength > scene.own_strength:
            tags.append("enemy_pressure")
        return "+".join(tags) if tags else "balanced_assessment"
