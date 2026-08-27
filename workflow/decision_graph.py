from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterator, List, TypedDict

from langgraph.graph import END, START, StateGraph

from agent_planner import AgentToolPlan
from memory import MemoryCase
from models import AgentGenerationRecord, BattlefieldScene, DebateMessage, ScoredProposal, StrategyProposal
from rag import KnowledgeSnippet
from tools import ToolResult
from trace import TraceEvent


class LangGraphRuntimeState(TypedDict):
    state: "DecisionGraphState"


@dataclass
class DecisionGraphState:
    scene: BattlefieldScene
    trace: List[TraceEvent]
    tool_calls: List[ToolResult] = field(default_factory=list)
    completed_nodes: List[str] = field(default_factory=list)
    tool_plan: AgentToolPlan | None = None
    knowledge_context: List[KnowledgeSnippet] = field(default_factory=list)
    memory_context: List[MemoryCase] = field(default_factory=list)
    risk_context: Dict[str, Any] = field(default_factory=dict)
    proposals: List[StrategyProposal] = field(default_factory=list)
    agent_generation_records: List[AgentGenerationRecord] = field(default_factory=list)
    grounding_evidence: Dict[str, Any] = field(default_factory=dict)
    messages: List[DebateMessage] = field(default_factory=list)
    weights: Dict[str, float] = field(default_factory=dict)
    llm_decision: Any | None = None
    ranking: List[ScoredProposal] = field(default_factory=list)
    plan_execution_audit: Dict[str, Any] = field(default_factory=dict)
    decision_audit: Dict[str, Any] = field(default_factory=dict)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "scene": self.scene.name,
            "completed_nodes": list(self.completed_nodes),
            "trace_steps": [event.step for event in self.trace],
            "tool_count": len(self.tool_calls),
            "proposal_count": len(self.proposals),
            "agent_generation_count": len(self.agent_generation_records),
            "grounding_status": self.grounding_evidence.get("status"),
            "ranking_count": len(self.ranking),
            "plan_execution_audit_status": self.plan_execution_audit.get("status"),
            "audit_status": self.decision_audit.get("overall_status"),
        }


@dataclass(frozen=True)
class DecisionGraphNode:
    name: str
    run: Callable[[DecisionGraphState], None]
    condition: Callable[[DecisionGraphState], bool] | None = None
    on_skip: Callable[[DecisionGraphState], None] | None = None

    def should_run(self, state: DecisionGraphState) -> bool:
        if self.condition is None:
            return True
        return self.condition(state)


class DecisionGraphRunner:
    def __init__(self, nodes: List[DecisionGraphNode]) -> None:
        self.nodes = nodes
        self.backend = "langgraph"
        self._compiled_graph = self._compile_graph()

    def node_names(self) -> List[str]:
        return [node.name for node in self.nodes]

    def run(self, state: DecisionGraphState) -> Iterator[DecisionGraphState]:
        runtime_state: LangGraphRuntimeState = {"state": state}
        for event in self._compiled_graph.stream(runtime_state):
            if not isinstance(event, dict):
                continue
            for graph_node, update in event.items():
                if not _is_executable_graph_node(graph_node):
                    continue
                updated_state = update.get("state") if isinstance(update, dict) else None
                if isinstance(updated_state, DecisionGraphState):
                    yield updated_state

    def _compile_graph(self):
        builder = StateGraph(LangGraphRuntimeState)
        router_names: List[str] = []

        for node in self.nodes:
            router_name = _router_name(node.name)
            run_name = _run_name(node.name)
            skip_name = _skip_name(node.name)
            router_names.append(router_name)

            builder.add_node(router_name, _router_node)
            builder.add_node(run_name, self._make_run_node(node))
            if node.condition is not None:
                builder.add_node(skip_name, self._make_skip_node(node))

        if not self.nodes:
            builder.add_edge(START, END)
            return builder.compile()

        builder.add_edge(START, router_names[0])
        for index, node in enumerate(self.nodes):
            router_name = router_names[index]
            run_name = _run_name(node.name)
            skip_name = _skip_name(node.name)
            next_target = router_names[index + 1] if index + 1 < len(router_names) else END

            if node.condition is None:
                builder.add_edge(router_name, run_name)
            else:
                builder.add_conditional_edges(
                    router_name,
                    self._make_route(node),
                    {"run": run_name, "skip": skip_name},
                )
                builder.add_edge(skip_name, next_target)
            builder.add_edge(run_name, next_target)

        return builder.compile()

    @staticmethod
    def _make_route(node: DecisionGraphNode) -> Callable[[LangGraphRuntimeState], str]:
        def route(runtime_state: LangGraphRuntimeState) -> str:
            return "run" if node.should_run(runtime_state["state"]) else "skip"

        return route

    @staticmethod
    def _make_run_node(node: DecisionGraphNode) -> Callable[[LangGraphRuntimeState], LangGraphRuntimeState]:
        def run_node(runtime_state: LangGraphRuntimeState) -> LangGraphRuntimeState:
            state = runtime_state["state"]
            node.run(state)
            state.completed_nodes.append(node.name)
            return {"state": state}

        return run_node

    @staticmethod
    def _make_skip_node(node: DecisionGraphNode) -> Callable[[LangGraphRuntimeState], LangGraphRuntimeState]:
        def skip_node(runtime_state: LangGraphRuntimeState) -> LangGraphRuntimeState:
            state = runtime_state["state"]
            if node.on_skip is not None:
                node.on_skip(state)
            state.completed_nodes.append(node.name)
            return {"state": state}

        return skip_node


def _router_node(runtime_state: LangGraphRuntimeState) -> LangGraphRuntimeState:
    return runtime_state


def _router_name(node_name: str) -> str:
    return f"{node_name}__router"


def _run_name(node_name: str) -> str:
    return f"{node_name}__run"


def _skip_name(node_name: str) -> str:
    return f"{node_name}__skip"


def _is_executable_graph_node(graph_node: str) -> bool:
    return graph_node.endswith("__run") or graph_node.endswith("__skip")
