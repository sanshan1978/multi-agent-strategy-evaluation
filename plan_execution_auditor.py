from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from agent_planner import AgentToolPlan
from tools import ToolResult


@dataclass(frozen=True)
class PlanExecutionFinding:
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
class PlanExecutionAudit:
    status: str
    planned_tools: List[str]
    actual_tools: List[str]
    skipped_tools: List[str]
    missing_tools: List[str]
    unexpected_tools: List[str]
    failed_tools: List[str]
    fallback_tools: List[str]
    sequence_match: bool
    plan_validation_status: str
    repaired_before_execution: bool
    findings: List[PlanExecutionFinding]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "planned_tools": self.planned_tools,
            "actual_tools": self.actual_tools,
            "skipped_tools": self.skipped_tools,
            "missing_tools": self.missing_tools,
            "unexpected_tools": self.unexpected_tools,
            "failed_tools": self.failed_tools,
            "fallback_tools": self.fallback_tools,
            "sequence_match": self.sequence_match,
            "plan_validation_status": self.plan_validation_status,
            "repaired_before_execution": self.repaired_before_execution,
            "findings": [finding.to_dict() for finding in self.findings],
            "summary": {
                "planned_count": len(self.planned_tools),
                "actual_count": len(self.actual_tools),
                "skipped_count": len(self.skipped_tools),
                "missing_count": len(self.missing_tools),
                "unexpected_count": len(self.unexpected_tools),
                "failed_count": len(self.failed_tools),
                "fallback_count": len(self.fallback_tools),
                "finding_count": len(self.findings),
            },
        }


class PlanExecutionAuditor:
    def audit(self, tool_plan: AgentToolPlan, tool_calls: List[ToolResult]) -> PlanExecutionAudit:
        planned_tools = [step.tool_name for step in tool_plan.steps]
        actual_tools = [call.tool_name for call in tool_calls]
        skipped_tools = [step.tool_name for step in tool_plan.skipped_steps]
        missing_tools = [tool for tool in planned_tools if tool not in actual_tools]
        unexpected_tools = [tool for tool in actual_tools if tool not in planned_tools]
        failed_tools = [call.tool_name for call in tool_calls if call.status != "completed"]
        fallback_tools = [call.tool_name for call in tool_calls if call.metadata.get("fallback_used") is True]
        sequence_match = actual_tools == planned_tools
        findings: List[PlanExecutionFinding] = []

        for tool_name in missing_tools:
            findings.append(
                PlanExecutionFinding(
                    code="missing_planned_tool",
                    severity="error",
                    message="planned tool was not executed by the workflow",
                    tool_name=tool_name,
                )
            )
        for tool_name in unexpected_tools:
            findings.append(
                PlanExecutionFinding(
                    code="unexpected_tool_call",
                    severity="warning",
                    message="tool was executed but not present in the repaired plan",
                    tool_name=tool_name,
                )
            )
        if not sequence_match:
            findings.append(
                PlanExecutionFinding(
                    code="tool_sequence_drift",
                    severity="warning",
                    message="actual tool execution order differs from repaired plan order",
                )
            )
        for tool_name in failed_tools:
            findings.append(
                PlanExecutionFinding(
                    code="tool_failed",
                    severity="warning",
                    message="tool execution failed and used policy handling",
                    tool_name=tool_name,
                )
            )
        for tool_name in fallback_tools:
            findings.append(
                PlanExecutionFinding(
                    code="tool_fallback_used",
                    severity="warning",
                    message="tool returned fallback output during execution",
                    tool_name=tool_name,
                )
            )
        if tool_plan.validation_status == "repaired":
            findings.append(
                PlanExecutionFinding(
                    code="plan_repaired_before_execution",
                    severity="info",
                    message="tool plan was repaired before workflow execution",
                )
            )

        status = "passed"
        if missing_tools or unexpected_tools or not sequence_match:
            status = "drift_detected"
        elif failed_tools or fallback_tools:
            status = "attention_required"

        return PlanExecutionAudit(
            status=status,
            planned_tools=planned_tools,
            actual_tools=actual_tools,
            skipped_tools=skipped_tools,
            missing_tools=missing_tools,
            unexpected_tools=unexpected_tools,
            failed_tools=failed_tools,
            fallback_tools=fallback_tools,
            sequence_match=sequence_match,
            plan_validation_status=tool_plan.validation_status,
            repaired_before_execution=tool_plan.validation_status == "repaired",
            findings=findings,
        )
