from __future__ import annotations

from main import PRESET_SCENES
from trace import TraceEvent
from workflow import DecisionGraphNode, DecisionGraphRunner, DecisionGraphState


def test_decision_graph_runner_executes_nodes_in_order() -> None:
    state = DecisionGraphState(scene=PRESET_SCENES["urban_fast_capture"], trace=[])

    def first_node(graph_state: DecisionGraphState) -> None:
        graph_state.trace.append(TraceEvent(step="first", message="first node"))

    def second_node(graph_state: DecisionGraphState) -> None:
        graph_state.trace.append(TraceEvent(step="second", message="second node"))

    runner = DecisionGraphRunner(
        [
            DecisionGraphNode("first", first_node),
            DecisionGraphNode("second", second_node),
        ]
    )

    snapshots = list(runner.run(state))

    assert runner.backend == "langgraph"
    assert runner.node_names() == ["first", "second"]
    assert snapshots[-1].completed_nodes == ["first", "second"]
    assert [event.step for event in snapshots[-1].trace] == ["first", "second"]
    assert snapshots[-1].snapshot()["completed_nodes"] == ["first", "second"]


def test_decision_graph_runner_supports_conditional_skip() -> None:
    state = DecisionGraphState(scene=PRESET_SCENES["urban_fast_capture"], trace=[])

    def should_skip(_: DecisionGraphState) -> bool:
        return False

    def skipped_node(graph_state: DecisionGraphState) -> None:
        graph_state.trace.append(TraceEvent(step="conditional", message="skipped", status="skipped"))

    def should_not_run(graph_state: DecisionGraphState) -> None:
        graph_state.trace.append(TraceEvent(step="conditional", message="ran"))

    runner = DecisionGraphRunner(
        [
            DecisionGraphNode(
                "conditional",
                should_not_run,
                condition=should_skip,
                on_skip=skipped_node,
            )
        ]
    )

    snapshots = list(runner.run(state))

    assert snapshots[-1].completed_nodes == ["conditional"]
    assert snapshots[-1].trace[0].status == "skipped"
    assert snapshots[-1].trace[0].message == "skipped"
