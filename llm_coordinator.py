from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List

from agent_planner import AgentToolPlan, SkippedToolStep, ToolPlanStep
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from logging_config import get_logger
from models import BattlefieldScene, DebateMessage, StrategyProposal, clamp
from settings import get_settings


logger = get_logger(__name__)

SYSTEM_PROMPT = """你是战场多智能体会议主持模型。
你会读取场景参数和多个候选策略，输出严格 JSON，不能输出任何额外文本。
JSON 结构要求:
{
  "messages": [
    {"from_agent": "A", "to_agent": "B", "content": "点评", "impact": 0.05}
  ],
  "adjustments": [
    {"agent_name": "A", "score_delta": 3.5, "confidence_delta": 0.04, "reason": "简要原因"}
  ],
  "recommended_agent": "A",
  "reason": "最终推荐理由"
}
约束:
1) impact 范围 [-0.2, 0.2]
2) score_delta 范围 [-15, 15]
3) confidence_delta 范围 [-0.25, 0.25]
4) 所有 agent 名称必须来自输入
5) content 和 reason 用中文，保持简洁
"""

TOOL_PLANNER_SYSTEM_PROMPT = """你是多智能体决策系统的工具规划器。
你会读取战场场景、可用工具目录和本地评分参考，输出严格 JSON，不要输出任何额外文本。
JSON 结构:
{
  "strategy": "planner strategy label",
  "steps": [
    {
      "tool_name": "knowledge_retrieval",
      "purpose": "why this tool is needed",
      "parameters": {"top_k": 3},
      "required": true
    }
  ],
  "skipped_tools": [
    {
      "tool_name": "memory_recall",
      "reason": "why this tool is not needed"
    }
  ]
}
约束:
1) tool_name 必须来自 tools 列表
2) 不要编造工具
3) knowledge_retrieval 和 memory_recall 的 top_k 范围是 1-6
4) risk_analysis 不需要额外参数
5) steps 按建议执行顺序排列
6) 所有中文说明保持简洁
"""


@dataclass
class LLMReview:
    messages: List[DebateMessage] = field(default_factory=list)
    score_deltas: Dict[str, float] = field(default_factory=dict)
    confidence_deltas: Dict[str, float] = field(default_factory=dict)
    recommended_agent: str | None = None
    reason: str | None = None
    error: str | None = None


@dataclass
class LLMToolPlanResult:
    plan: AgentToolPlan | None = None
    error: str | None = None


class LLMCoordinator:
    def __init__(self, api_key: str, base_url: str, model: str, timeout_sec: int = 35) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_sec = timeout_sec
        self.client = ChatOpenAI(
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=0,
            max_retries=2,
            timeout=self.timeout_sec,
        )

    @classmethod
    def from_env(cls, model: str | None = None) -> "LLMCoordinator | None":
        settings = get_settings(model_override=model)
        if not settings.has_api_key:
            logger.info("LLM coordinator disabled: no API key detected")
            return None
        logger.info("LLM coordinator enabled: model=%s base_url=%s", settings.model, settings.base_url)
        return cls(
            api_key=settings.api_key,
            base_url=settings.base_url,
            model=settings.model,
            timeout_sec=settings.timeout_sec,
        )

    def review(
        self,
        scene: BattlefieldScene,
        proposals: List[StrategyProposal],
        weights: Dict[str, float],
    ) -> LLMReview:
        try:
            response = self.client.invoke(
                [
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(content=self._build_user_prompt(scene, proposals, weights)),
                ]
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM review failed: %s", exc)
            return LLMReview(error=self._friendly_network_error(str(exc)))

        content = self._extract_content(response.content)
        parsed = self._load_json_content(content)
        if parsed is None:
            logger.warning("LLM review returned non-JSON content")
            return LLMReview(error="模型返回内容无法解析为 JSON 对象")
        return self._to_review(parsed, proposals)

    def generate_strategy_payload(self, *, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        response = self.client.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
        )
        content = self._extract_content(response.content)
        parsed = self._load_json_content(content)
        if parsed is None:
            raise ValueError("strategy agent response is not a JSON object")
        return parsed

    def plan_tools(
        self,
        scene: BattlefieldScene,
        tool_specs: List[Dict[str, Any]],
        fallback_plan: AgentToolPlan,
    ) -> LLMToolPlanResult:
        try:
            response = self.client.invoke(
                [
                    SystemMessage(content=TOOL_PLANNER_SYSTEM_PROMPT),
                    HumanMessage(content=self._build_tool_planner_prompt(scene, tool_specs, fallback_plan)),
                ]
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM tool planner failed: %s", exc)
            return LLMToolPlanResult(error=self._friendly_network_error(str(exc)))

        content = self._extract_content(response.content)
        parsed = self._load_json_content(content)
        if parsed is None:
            logger.warning("LLM tool planner returned non-JSON content")
            return LLMToolPlanResult(error="模型工具规划返回内容无法解析为 JSON")
        try:
            plan = self._to_tool_plan(parsed, tool_specs, fallback_plan)
        except ValueError as exc:
            logger.warning("LLM tool planner returned invalid plan: %s", exc)
            return LLMToolPlanResult(error=str(exc))
        return LLMToolPlanResult(plan=plan)

    @staticmethod
    def _friendly_network_error(message: str) -> str:
        if "UNEXPECTED_EOF_WHILE_READING" in message or "EOF occurred in violation of protocol" in message:
            return (
                "SSL 连接被中断，通常与网络代理、网关拦截、OPENAI_BASE_URL 协议配置或服务端临时断开有关。"
                f"原始错误: {message}"
            )
        return message

    @staticmethod
    def _extract_content(content: object) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text") or item.get("content")
                    if isinstance(text, str):
                        parts.append(text)
                elif isinstance(item, str):
                    parts.append(item)
            return "\n".join(parts)
        return ""

    @staticmethod
    def _load_json_content(content: str) -> Dict[str, object] | None:
        text = content.strip()
        if not text:
            return None
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            parsed = json.loads(text[start : end + 1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return None
        return None

    @staticmethod
    def _bound(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def _to_review(self, data: Dict[str, object], proposals: List[StrategyProposal]) -> LLMReview:
        known_agents = {p.agent_name for p in proposals}
        review = LLMReview()

        raw_messages = data.get("messages", [])
        if isinstance(raw_messages, list):
            for item in raw_messages[:24]:
                if not isinstance(item, dict):
                    continue
                from_agent = str(item.get("from_agent", "模型裁决"))
                to_agent = str(item.get("to_agent", ""))
                content = str(item.get("content", "")).strip()
                if to_agent not in known_agents or not content:
                    continue
                try:
                    impact = float(item.get("impact", 0.0))
                except (TypeError, ValueError):
                    impact = 0.0
                review.messages.append(
                    DebateMessage(
                        from_agent=from_agent,
                        to_agent=to_agent,
                        content=content,
                        impact=self._bound(impact, -0.2, 0.2),
                    )
                )

        raw_adjustments = data.get("adjustments", [])
        if isinstance(raw_adjustments, list):
            for item in raw_adjustments[:24]:
                if not isinstance(item, dict):
                    continue
                agent_name = str(item.get("agent_name", "")).strip()
                if agent_name not in known_agents:
                    continue
                try:
                    score_delta = float(item.get("score_delta", 0.0))
                except (TypeError, ValueError):
                    score_delta = 0.0
                try:
                    confidence_delta = float(item.get("confidence_delta", 0.0))
                except (TypeError, ValueError):
                    confidence_delta = 0.0
                review.score_deltas[agent_name] = review.score_deltas.get(agent_name, 0.0) + self._bound(
                    score_delta, -15.0, 15.0
                )
                review.confidence_deltas[agent_name] = review.confidence_deltas.get(agent_name, 0.0) + self._bound(
                    confidence_delta, -0.25, 0.25
                )

        recommended = str(data.get("recommended_agent", "")).strip()
        if recommended in known_agents:
            review.recommended_agent = recommended
        reason = str(data.get("reason", "")).strip()
        if reason:
            review.reason = reason
        return review

    def _to_tool_plan(
        self,
        data: Dict[str, object],
        tool_specs: List[Dict[str, Any]],
        fallback_plan: AgentToolPlan,
    ) -> AgentToolPlan:
        available_tools = [str(item.get("name", "")).strip() for item in tool_specs if isinstance(item, dict)]
        available = {name for name in available_tools if name}
        if not available:
            raise ValueError("no available tools for LLM planner")

        raw_steps = data.get("steps", [])
        if not isinstance(raw_steps, list):
            raise ValueError("LLM tool plan steps must be a list")

        fallback_scores = self._fallback_tool_scores(fallback_plan)
        steps: List[ToolPlanStep] = []
        seen: set[str] = set()
        sequence = 1
        for item in raw_steps[: len(available_tools)]:
            if not isinstance(item, dict):
                continue
            tool_name = str(item.get("tool_name", "")).strip()
            if tool_name not in available or tool_name in seen:
                continue
            score = fallback_scores.get(tool_name, {"need_score": 0.0, "threshold": 0.0})
            steps.append(
                ToolPlanStep(
                    sequence=sequence,
                    tool_name=tool_name,
                    purpose=self._clean_text(item.get("purpose"), default=f"llm_selected_{tool_name}"),
                    parameters=self._sanitize_tool_parameters(tool_name, item.get("parameters")),
                    required=bool(item.get("required", True)),
                    need_score=float(score["need_score"]),
                    threshold=float(score["threshold"]),
                )
            )
            seen.add(tool_name)
            sequence += 1

        if not steps:
            raise ValueError("LLM tool plan did not select any valid tools")

        skipped_reasons = self._explicit_skip_reasons(data.get("skipped_tools"))
        skipped_steps: List[SkippedToolStep] = []
        for tool_name in available_tools:
            if tool_name in seen:
                continue
            score = fallback_scores.get(tool_name, {"need_score": 0.0, "threshold": 0.0})
            skipped_steps.append(
                SkippedToolStep(
                    tool_name=tool_name,
                    reason=skipped_reasons.get(tool_name, "not_selected_by_llm_planner"),
                    condition="llm_planner_selected_other_tools",
                    need_score=float(score["need_score"]),
                    threshold=float(score["threshold"]),
                )
            )

        strategy = self._clean_text(data.get("strategy"), default=fallback_plan.strategy)
        return AgentToolPlan(
            objective=fallback_plan.objective,
            strategy=strategy,
            steps=steps,
            skipped_steps=skipped_steps,
            planner_source="llm-planner",
            planner_model=self.model,
        )

    @staticmethod
    def _fallback_tool_scores(fallback_plan: AgentToolPlan) -> Dict[str, Dict[str, float]]:
        scores: Dict[str, Dict[str, float]] = {}
        for step in fallback_plan.steps:
            scores[step.tool_name] = {"need_score": step.need_score, "threshold": step.threshold}
        for step in fallback_plan.skipped_steps:
            scores[step.tool_name] = {"need_score": step.need_score, "threshold": step.threshold}
        return scores

    @staticmethod
    def _explicit_skip_reasons(raw_skips: object) -> Dict[str, str]:
        reasons: Dict[str, str] = {}
        if not isinstance(raw_skips, list):
            return reasons
        for item in raw_skips:
            if not isinstance(item, dict):
                continue
            tool_name = str(item.get("tool_name", "")).strip()
            reason = str(item.get("reason", "")).strip()
            if tool_name and reason:
                reasons[tool_name] = reason[:160]
        return reasons

    @staticmethod
    def _clean_text(value: object, default: str) -> str:
        text = str(value or "").strip()
        return text[:160] if text else default

    @staticmethod
    def _sanitize_tool_parameters(tool_name: str, raw_parameters: object) -> Dict[str, Any]:
        if not isinstance(raw_parameters, dict):
            raw_parameters = {}
        if tool_name in {"knowledge_retrieval", "memory_recall"}:
            raw_top_k = raw_parameters.get("top_k", 3)
            try:
                top_k = int(raw_top_k)
            except (TypeError, ValueError):
                top_k = 3
            return {"top_k": max(1, min(top_k, 6))}
        return {}

    @staticmethod
    def _build_user_prompt(scene: BattlefieldScene, proposals: List[StrategyProposal], weights: Dict[str, float]) -> str:
        payload = {
            "scene": {
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
            },
            "weights": weights,
            "proposals": [
                {
                    "agent_name": p.agent_name,
                    "strategy_name": p.strategy_name,
                    "summary": p.summary,
                    "actions": p.actions,
                    "metric_scores": {k: clamp(v, 0.0, 100.0) for k, v in p.metric_scores.items()},
                    "rationale": p.rationale,
                    "confidence": p.confidence,
                    "peer_support": p.peer_support,
                }
                for p in proposals
            ],
        }
        return (
            "请基于以下输入完成多智能体互评与裁决，严格返回 JSON:\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )

    @staticmethod
    def _build_tool_planner_prompt(
        scene: BattlefieldScene,
        tool_specs: List[Dict[str, Any]],
        fallback_plan: AgentToolPlan,
    ) -> str:
        payload = {
            "scene": {
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
            },
            "tools": tool_specs,
            "local_score_reference": fallback_plan.to_dict(),
        }
        return (
            "请基于以下输入生成工具调用计划。可以参考 local_score_reference，但最终只返回指定 JSON:\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
        )
