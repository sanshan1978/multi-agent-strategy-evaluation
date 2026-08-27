# Parallel LLM Strategy Agents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Upgrade the five deterministic strategy agents into five independently invoked, concurrently executed Qwen strategy agents with role-local fallback and structured generation trace.

**Architecture:** Keep `agents.py` as the deterministic baseline and fallback provider. Add a focused `llm_strategy_agents.py` domain service that validates model JSON, combines bounded adjustments with rule metrics, and executes five calls through a bounded thread pool; integrate its batch result into the existing sequential LangGraph node without changing public request endpoints.

**Tech Stack:** Python 3.13, Pydantic 2.12, LangChain `ChatOpenAI`, Qwen OpenAI-compatible API, `ThreadPoolExecutor`, LangGraph, FastAPI, pytest.

## Global Constraints

- Use the configured `qwen3.7-plus` model for all five strategy-agent calls.
- A complete online request may make at most seven Qwen calls: one Planner, five strategy agents and one Reviewer.
- Default `MESSAGE_TALK_AGENT_MAX_WORKERS` is `5`; accepted range is `1..5`.
- `llm_mode=off` makes zero strategy-agent model calls.
- `llm_mode=auto` falls back only the failed role; missing credentials fall back all roles.
- `llm_mode=on` fails the request if any role fails.
- Final metrics equal deterministic baselines plus adjustments clamped to `[-10, 10]`, then scores are clamped to `[0, 100]`.
- Model output uses Pydantic `extra="forbid"`.
- Knowledge titles and memory IDs must be subsets of supplied context.
- Preserve existing FastAPI request endpoints, canonical five-agent order and rule-mode behavior.
- Do not log prompts, API keys or unrestricted evidence content.
- This directory is not a Git repository; replace commit steps with explicit verification checkpoints and do not initialize Git as part of this feature.

---

### Task 1: Runtime Setting and Generation Record Contract

**Files:**
- Modify: `settings.py`
- Modify: `models.py`
- Modify: `workflow/decision_graph.py`
- Modify: `.env.example`
- Modify: `docker-compose.yml`
- Test: `tests/test_settings.py`
- Test: `tests/test_decision_engine.py`

**Interfaces:**
- Produces: `AppSettings.agent_max_workers: int`.
- Produces: `AgentGenerationRecord.to_dict() -> Dict[str, Any]`.
- Produces: `DecisionGraphState.agent_generation_records: List[AgentGenerationRecord]`.

- [x] **Step 1: Write failing settings and record tests**

Add these tests:

```python
from models import AgentGenerationRecord


def test_agent_max_workers_defaults_to_five(monkeypatch) -> None:
    monkeypatch.delenv("MESSAGE_TALK_AGENT_MAX_WORKERS", raising=False)
    assert get_settings().agent_max_workers == 5


def test_agent_max_workers_is_bounded(monkeypatch) -> None:
    monkeypatch.setenv("MESSAGE_TALK_AGENT_MAX_WORKERS", "99")
    assert get_settings().agent_max_workers == 5
    monkeypatch.setenv("MESSAGE_TALK_AGENT_MAX_WORKERS", "0")
    assert get_settings().agent_max_workers == 1


def test_agent_generation_record_serializes_optional_metadata() -> None:
    record = AgentGenerationRecord(
        agent_name="强攻智能体",
        strategy_name="快速正面突破",
        generation_mode="rule-fallback",
        model="fake-qwen",
        duration_ms=12.5,
        validation_status="failed",
        fallback_reason="invalid_json",
        knowledge_sources=["城市环境"],
        memory_sources=[3],
        metric_adjustments={"success_prob": 0.0},
    )
    assert record.to_dict()["fallback_reason"] == "invalid_json"
```

- [x] **Step 2: Run focused tests and verify RED**

Run:

```powershell
pytest tests/test_settings.py tests/test_decision_engine.py -q
```

Expected: failures for missing `agent_max_workers` and `AgentGenerationRecord`.

- [x] **Step 3: Implement settings and record types**

Add:

```python
DEFAULT_AGENT_MAX_WORKERS = 5


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
```

Read the worker setting with `_read_positive_int`, then clamp with `min(5, value)`. Add `agent_generation_records` to `DecisionGraphState` with an empty-list factory. Document the environment variable in `.env.example` and pass `${MESSAGE_TALK_AGENT_MAX_WORKERS:-5}` into the API container.

- [x] **Step 4: Run focused tests and verify GREEN**

Run:

```powershell
pytest tests/test_settings.py tests/test_decision_engine.py -q
```

Expected: all existing tests plus the new contract tests pass.

- [x] **Step 5: Verification checkpoint**

Run:

```powershell
python -m compileall settings.py models.py workflow
```

Expected: exit code `0`.

---

### Task 2: Qwen Strategy-Agent Transport

**Files:**
- Modify: `llm_coordinator.py`
- Test: `tests/test_decision_engine.py`

**Interfaces:**
- Produces: `LLMCoordinator.generate_strategy_payload(*, system_prompt: str, user_prompt: str) -> Dict[str, Any]`.
- Consumes: existing `ChatOpenAI` client and `_load_json_content()`.

- [x] **Step 1: Write failing transport tests**

Use a fake client response:

```python
class FakeResponse:
    content = '{"summary":"方案","actions":["A","B"],"rationale":"依据","used_knowledge_titles":[],"used_memory_ids":[],"metric_adjustments":{},"confidence":0.7}'


class FakeInvokeClient:
    def invoke(self, messages):  # noqa: ANN001
        assert len(messages) == 2
        return FakeResponse()


def test_generate_strategy_payload_returns_json_object() -> None:
    coordinator = object.__new__(LLMCoordinator)
    coordinator.client = FakeInvokeClient()
    payload = coordinator.generate_strategy_payload(system_prompt="role", user_prompt="context")
    assert payload["summary"] == "方案"


def test_generate_strategy_payload_rejects_non_json() -> None:
    coordinator = object.__new__(LLMCoordinator)
    coordinator.client = FakeNonJsonClient()
    with pytest.raises(ValueError, match="JSON"):
        coordinator.generate_strategy_payload(system_prompt="role", user_prompt="context")
```

- [x] **Step 2: Run focused test and verify RED**

Run:

```powershell
pytest tests/test_decision_engine.py -k "generate_strategy_payload" -q
```

Expected: failure because the method does not exist.

- [x] **Step 3: Implement the narrow transport method**

Add:

```python
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
```

Do not catch transport exceptions here; the parallel runner owns per-role error isolation and mode semantics.

- [x] **Step 4: Run focused test and verify GREEN**

Run:

```powershell
pytest tests/test_decision_engine.py -k "generate_strategy_payload" -q
```

Expected: both transport tests pass.

---

### Task 3: Single LLM Strategy Agent and Structured Validation

**Files:**
- Create: `llm_strategy_agents.py`
- Create: `tests/test_llm_strategy_agents.py`

**Interfaces:**
- Consumes: `BaseAgent.propose(scene) -> StrategyProposal` as baseline.
- Consumes: a client with `model` and `generate_strategy_payload(...)`.
- Produces: `LLMStrategyAgent.generate(...) -> StrategyAgentGenerationResult`.
- Produces: `build_default_strategy_profiles() -> Dict[str, StrategyAgentProfile]`.

- [x] **Step 1: Write failing schema, role and conversion tests**

Cover these exact behaviors:

```python
def test_default_profiles_cover_all_rule_agents() -> None:
    profiles = build_default_strategy_profiles()
    assert set(profiles) == {agent.name for agent in build_default_agents()}
    assert len({profile.role_prompt for profile in profiles.values()}) == 5


def test_payload_forbids_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        LLMStrategyProposalPayload.model_validate({**valid_payload(), "unexpected": True})


def test_llm_agent_uses_bounded_adjustments_and_allowed_evidence() -> None:
    client = FakeStrategyClient(
        payload={
            **valid_payload(),
            "used_knowledge_titles": ["允许标题", "伪造标题"],
            "used_memory_ids": [7, 999],
            "metric_adjustments": {"success_prob": 99, "risk_control": -99},
        }
    )
    result = make_llm_agent(client).generate(
        scene=scene(),
        baseline=baseline(),
        knowledge_context=[snippet(title="允许标题")],
        memory_context=[memory(record_id=7)],
        risk_context={"risk_level": "high"},
    )
    assert result.proposal.metric_scores["success_prob"] == 100.0
    assert result.proposal.knowledge_sources == ["允许标题"]
    assert result.proposal.memory_sources == [7]
    assert result.record.metric_adjustments["success_prob"] == 10.0
```

Add explicit boundary tests:

```python
def test_payload_requires_two_to_six_actions() -> None:
    with pytest.raises(ValidationError):
        LLMStrategyProposalPayload.model_validate({**valid_payload(), "actions": ["only-one"]})


def test_payload_rejects_unknown_metric_name() -> None:
    with pytest.raises(ValidationError, match="unknown metric"):
        LLMStrategyProposalPayload.model_validate(
            {**valid_payload(), "metric_adjustments": {"invented_metric": 5}}
        )


def test_prompt_context_is_excerpted() -> None:
    agent = make_llm_agent(RecordingStrategyClient(payload=valid_payload()))
    agent.generate(
        scene=scene(),
        baseline=baseline(),
        knowledge_context=[snippet(title="允许标题", content="x" * 5000)],
        memory_context=[],
        risk_context={},
    )
    assert "x" * 501 not in agent.client.user_prompts[0]
```

- [x] **Step 2: Run new test module and verify RED**

Run:

```powershell
pytest tests/test_llm_strategy_agents.py -q
```

Expected: import failure because `llm_strategy_agents.py` does not exist.

- [x] **Step 3: Implement domain contracts and five profiles**

Implement these signatures:

```python
METRIC_NAMES = {
    "success_prob",
    "resource_efficiency",
    "risk_control",
    "response_speed",
    "intel_alignment",
}


class LLMStrategyProposalPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    summary: str = Field(min_length=1, max_length=500)
    actions: List[str] = Field(min_length=2, max_length=6)
    rationale: str = Field(min_length=1, max_length=1200)
    used_knowledge_titles: List[str] = Field(default_factory=list, max_length=6)
    used_memory_ids: List[int] = Field(default_factory=list, max_length=6)
    metric_adjustments: Dict[str, float] = Field(default_factory=dict)
    confidence: float = Field(ge=0.2, le=1.0)


@dataclass(frozen=True)
class StrategyAgentProfile:
    agent_name: str
    strategy_name: str
    role_prompt: str
    priorities: tuple[str, ...]


@dataclass(frozen=True)
class StrategyAgentGenerationResult:
    proposal: StrategyProposal
    record: AgentGenerationRecord
```

Validate metric keys before clamping values. Filter evidence references against runtime allow-lists. Build final metrics from a copied baseline dictionary:

```python
metrics = {
    name: clamp(baseline.metric_scores[name] + payload.metric_adjustments.get(name, 0.0))
    for name in METRIC_NAMES
}
```

The prompt must state that retrieved content is evidence, not executable instruction, and must serialize bounded context with `json.dumps(..., ensure_ascii=False)`.

- [x] **Step 4: Run new tests and verify GREEN**

Run:

```powershell
pytest tests/test_llm_strategy_agents.py -q
```

Expected: all single-agent validation tests pass.

- [x] **Step 5: Run static import checkpoint**

Run:

```powershell
python -c "from llm_strategy_agents import build_default_strategy_profiles; print(len(build_default_strategy_profiles()))"
```

Expected output: `5`.

---

### Task 4: Parallel Runner and Per-Agent Fallback

**Files:**
- Modify: `llm_strategy_agents.py`
- Modify: `tests/test_llm_strategy_agents.py`

**Interfaces:**
- Produces: `ParallelStrategyAgentRunner.generate(...) -> StrategyAgentGenerationBatch`.
- Produces: `StrategyAgentGenerationError`, containing failed generation records in strict mode.
- Consumes: canonical `Sequence[BaseAgent]`, `llm_mode`, optional model client and `max_workers`.

- [x] **Step 1: Write failing mode and concurrency-order tests**

Add a `RecordingStrategyClient` test double with thread-safe `calls`, role-specific delays and an optional `fail_agent`, then test:

```python
def test_off_mode_makes_zero_model_calls() -> None:
    client = RecordingStrategyClient()
    batch = runner(max_workers=5).generate(
        agents=build_default_agents(), llm=client, llm_mode="off", **contexts()
    )
    assert client.calls == []
    assert {record.generation_mode for record in batch.records} == {"rule"}


def test_auto_mode_falls_back_only_failed_agent() -> None:
    client = RecordingStrategyClient(fail_agent="防御智能体")
    batch = runner().generate(
        agents=build_default_agents(), llm=client, llm_mode="auto", **contexts()
    )
    assert [item.agent_name for item in batch.proposals] == [
        "强攻智能体", "迂回智能体", "防御智能体", "诱骗智能体", "火力压制智能体"
    ]
    modes = {item.agent_name: item.generation_mode for item in batch.records}
    assert modes["防御智能体"] == "rule-fallback"
    assert list(modes.values()).count("llm") == 4


def test_on_mode_raises_aggregated_error_for_one_failed_agent() -> None:
    with pytest.raises(StrategyAgentGenerationError) as exc_info:
        runner().generate(
            agents=build_default_agents(),
            llm=RecordingStrategyClient(fail_agent="防御智能体"),
            llm_mode="on",
            **contexts(),
        )
    assert [record.agent_name for record in exc_info.value.failures] == ["防御智能体"]
```

Add missing-client and completion-order tests:

```python
def test_auto_mode_without_client_returns_five_rule_proposals() -> None:
    batch = runner().generate(
        agents=build_default_agents(), llm=None, llm_mode="auto", **contexts()
    )
    assert len(batch.proposals) == 5
    assert {record.generation_mode for record in batch.records} == {"rule-fallback"}
    assert {record.fallback_reason for record in batch.records} == {"missing_api_key"}


def test_parallel_completion_does_not_change_agent_order() -> None:
    client = RecordingStrategyClient(
        delays={"强攻智能体": 0.05, "迂回智能体": 0.01, "防御智能体": 0.03}
    )
    batch = runner(max_workers=5).generate(
        agents=build_default_agents(), llm=client, llm_mode="auto", **contexts()
    )
    assert [proposal.agent_name for proposal in batch.proposals] == [
        "强攻智能体", "迂回智能体", "防御智能体", "诱骗智能体", "火力压制智能体"
    ]
```

- [x] **Step 2: Run parallel-runner tests and verify RED**

Run:

```powershell
pytest tests/test_llm_strategy_agents.py -k "mode or fallback or order" -q
```

Expected: failures because runner types do not exist.

- [x] **Step 3: Implement bounded parallel execution**

Implement:

```python
@dataclass(frozen=True)
class StrategyAgentGenerationBatch:
    proposals: List[StrategyProposal]
    records: List[AgentGenerationRecord]
    duration_ms: float


class ParallelStrategyAgentRunner:
    def __init__(self, max_workers: int = 5) -> None:
        self.max_workers = max(1, min(int(max_workers), 5))

    def generate(
        self,
        *,
        agents: Sequence[BaseAgent],
        llm: StrategyAgentModelClient | None,
        llm_mode: str,
        scene: BattlefieldScene,
        knowledge_context: Sequence[KnowledgeSnippet],
        memory_context: Sequence[MemoryCase],
        risk_context: Dict[str, Any],
    ) -> StrategyAgentGenerationBatch:
        started_at = time.perf_counter()
        baselines = [agent.propose(scene) for agent in agents]
        if llm_mode == "off" or llm is None:
            reason = None if llm_mode == "off" else "missing_api_key"
            mode = "rule" if llm_mode == "off" else "rule-fallback"
            records = [
                AgentGenerationRecord(
                    agent_name=proposal.agent_name,
                    strategy_name=proposal.strategy_name,
                    generation_mode=mode,
                    fallback_reason=reason,
                    knowledge_sources=[item.title for item in knowledge_context],
                    memory_sources=[item.record_id for item in memory_context],
                )
                for proposal in baselines
            ]
            return StrategyAgentGenerationBatch(
                proposals=baselines,
                records=records,
                duration_ms=(time.perf_counter() - started_at) * 1000,
            )

        results: Dict[int, StrategyAgentGenerationResult] = {}
        failures: Dict[int, AgentGenerationRecord] = {}
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(agents))) as executor:
            future_indexes = {
                executor.submit(
                    LLMStrategyAgent(profile=profiles[agent.name], client=llm).generate,
                    scene=scene,
                    baseline=baselines[index],
                    knowledge_context=knowledge_context,
                    memory_context=memory_context,
                    risk_context=risk_context,
                ): index
                for index, agent in enumerate(agents)
            }
            for future in as_completed(future_indexes):
                index = future_indexes[future]
                try:
                    results[index] = future.result()
                except Exception as exc:  # noqa: BLE001
                    baseline = baselines[index]
                    failures[index] = AgentGenerationRecord(
                        agent_name=baseline.agent_name,
                        strategy_name=baseline.strategy_name,
                        generation_mode="rule-fallback",
                        model=llm.model,
                        validation_status="failed",
                        fallback_reason=_safe_error_code(exc),
                    )

        if failures and llm_mode == "on":
            raise StrategyAgentGenerationError([failures[index] for index in sorted(failures)])

        proposals = [
            results[index].proposal if index in results else _attach_rule_sources(
                baselines[index], knowledge_context, memory_context
            )
            for index in range(len(agents))
        ]
        records = [
            results[index].record if index in results else failures[index]
            for index in range(len(agents))
        ]
        return StrategyAgentGenerationBatch(
            proposals=proposals,
            records=records,
            duration_ms=(time.perf_counter() - started_at) * 1000,
        )
```

Create all baseline proposals on the orchestration thread before submitting futures. Map each future to its canonical index, catch each exception independently, and reconstruct proposals and records by index. Use `with ThreadPoolExecutor(max_workers=min(self.max_workers, len(agents))) as executor:` so shutdown occurs on every path.

In strict mode, wait for all submitted futures, collect every failure record, then raise one `StrategyAgentGenerationError` so diagnostics are not lost.

- [x] **Step 4: Run runner tests and verify GREEN**

Run:

```powershell
pytest tests/test_llm_strategy_agents.py -q
```

Expected: all validation, mode, fallback and ordering tests pass.

---

### Task 5: DecisionEngine and LangGraph State Integration

**Files:**
- Modify: `decision_engine.py`
- Modify: `workflow/decision_graph.py`
- Modify: `tests/test_decision_engine.py`

**Interfaces:**
- Consumes: `ParallelStrategyAgentRunner.generate(...)`.
- Produces: `DecisionResult.agent_generation_records`.
- Produces: `generate_proposals` Trace metadata with `llm_success_count`, `fallback_count`, `duration_ms`, `max_agent_duration_ms`, and `agents`.

- [x] **Step 1: Write failing engine integration tests**

Extend a fake coordinator with `generate_strategy_payload()` and test:

```python
def test_engine_generates_five_llm_proposals_with_trace() -> None:
    engine = DecisionEngine(llm_mode="off")
    engine.llm_mode = "auto"
    engine.llm = FakeCompleteLLM()
    result = engine.run(PRESET_SCENES["urban_fast_capture"])
    assert len(result.agent_generation_records) == 5
    assert {record.generation_mode for record in result.agent_generation_records} == {"llm"}
    generation_trace = next(event for event in result.trace if event.step == "generate_proposals")
    assert generation_trace.metadata["llm_success_count"] == 5
    assert generation_trace.metadata["fallback_count"] == 0


def test_engine_auto_mode_keeps_four_llm_proposals_when_one_fails() -> None:
    engine = make_engine_with_llm(FakeCompleteLLM(fail_agent="防御智能体"), mode="auto")
    result = engine.run(PRESET_SCENES["urban_fast_capture"])
    assert sum(record.generation_mode == "llm" for record in result.agent_generation_records) == 4
    assert sum(record.generation_mode == "rule-fallback" for record in result.agent_generation_records) == 1


def test_engine_llm_agents_select_grounding_sources() -> None:
    result = make_engine_with_llm(FakeCompleteLLM(use_first_evidence=True), mode="auto").run(scene)
    assert all(proposal.proposal.knowledge_sources for proposal in result.ranking)
    assert result.grounding_evidence["summary"]["grounded_proposal_count"] == 5
```

Keep existing `llm_mode=off` workflow and Trace-order assertions unchanged.

- [x] **Step 2: Run focused engine tests and verify RED**

Run:

```powershell
pytest tests/test_decision_engine.py -k "generation or five_llm or grounding_sources" -q
```

Expected: failures for missing result records and old proposal path.

- [x] **Step 3: Wire runner into the existing graph node**

In `DecisionEngine.__init__`, load `get_settings()` once for `agent_max_workers` and create or inject `ParallelStrategyAgentRunner`. Extend the constructor with:

```python
strategy_agent_runner: ParallelStrategyAgentRunner | None = None
```

Change the node to pass all upstream context:

```python
batch = self.strategy_agent_runner.generate(
    agents=self.agents,
    llm=self.llm,
    llm_mode=self.llm_mode,
    scene=state.scene,
    knowledge_context=state.knowledge_context,
    memory_context=state.memory_context,
    risk_context=state.risk_context,
)
state.proposals = batch.proposals
state.agent_generation_records = batch.records
```

Append one Trace event using only structured generation records, counts and timing. Add records to `DecisionResult` construction. Remove the old unconditional `_attach_knowledge_context` and `_attach_memory_context` behavior for LLM results; the runner supplies selected sources, while rule/fallback results retain all available source references.

- [x] **Step 4: Run engine tests and verify GREEN**

Run:

```powershell
pytest tests/test_decision_engine.py -q
```

Expected: all engine tests pass, including prior rule-mode and Planner tests.

- [x] **Step 5: Verify default offline flow**

Run:

```powershell
python main.py --llm-mode off --no-messages
```

Expected: five ranked rule proposals, no external model call and successful completion.

---

### Task 6: API, Serialization and SSE Compatibility

**Files:**
- Modify: `serializers.py`
- Modify: `schemas.py`
- Modify: `tests/test_serializers.py`
- Modify: `tests/test_api_fastapi.py`

**Interfaces:**
- Produces: additive `agent_generation` field in `result_to_dict()` and `DecisionResponse`.
- Preserves: `progress`, `result`, `done`, `error` SSE event names.

- [x] **Step 1: Write failing response-contract tests**

Update serializer expectations and add:

```python
def test_result_serializer_exposes_agent_generation_records() -> None:
    data = result_to_dict(DecisionEngine(llm_mode="off").run(PRESET_SCENES["urban_fast_capture"]))
    assert len(data["agent_generation"]) == 5
    assert {item["generation_mode"] for item in data["agent_generation"]} == {"rule"}
    assert {
        "agent_name", "strategy_name", "generation_mode", "model",
        "duration_ms", "validation_status", "fallback_reason",
        "knowledge_sources", "memory_sources", "metric_adjustments",
    } <= set(data["agent_generation"][0])
```

Extend the FastAPI tests with these assertions:

```python
assert len(response.json()["agent_generation"]) == 5

text = stream_response.text
assert '"agent_generation"' in text
assert "event: progress" in text
assert "event: result" in text
assert "event: done" in text
assert "event: error" not in text
```

- [x] **Step 2: Run API contract tests and verify RED**

Run:

```powershell
pytest tests/test_serializers.py tests/test_api_fastapi.py -q
```

Expected: failures because the new additive field is missing.

- [x] **Step 3: Implement serializers and Pydantic response schema**

Add:

```python
class AgentGenerationRecordSchema(BaseModel):
    agent_name: str
    strategy_name: str
    generation_mode: str
    model: str | None = None
    duration_ms: float
    validation_status: str
    fallback_reason: str | None = None
    knowledge_sources: List[str]
    memory_sources: List[int]
    metric_adjustments: Dict[str, float]
```

Add to `DecisionResponse`:

```python
agent_generation: List[AgentGenerationRecordSchema] = Field(
    description="五个策略 Agent 的生成模式、模型、耗时、证据和 fallback 记录"
)
```

Serialize with:

```python
"agent_generation": [record.to_dict() for record in result.agent_generation_records],
```

- [x] **Step 4: Run API contract tests and verify GREEN**

Run:

```powershell
pytest tests/test_serializers.py tests/test_api_fastapi.py -q
```

Expected: all serializer and API tests pass; SSE still contains all four event names.

---

### Task 7: Full Regression, Live Qwen Smoke Test and Documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/实习面试项目介绍与问答.md`
- Modify: `OPTIMIZATION_LOG.md`
- Modify: this plan file to mark completed checkboxes during execution

**Interfaces:**
- Documents: exact LLM Agent behavior, fallback boundary, call count and verified evidence.
- Verifies: deterministic suite and optional live Qwen path.

- [x] **Step 1: Run the full deterministic suite**

Run:

```powershell
pytest -q
```

Expected: all tests pass. Record the exact new test count and any warnings; do not reuse the old `110 passed` number.

- [x] **Step 2: Run compile verification**

Run:

```powershell
python -m compileall . -q
```

Expected: exit code `0`.

- [x] **Step 3: Run a real Qwen smoke case when credentials and network are available**

Use the existing environment without printing secret values:

```powershell
python main.py --llm-mode auto --scenario urban_fast_capture --no-messages
```

Verify from result/Trace, not assumptions:

- Five `agent_generation` records exist.
- Successful records use `generation_mode=llm` and model `qwen3.7-plus`.
- Each role has distinct summary/actions.
- At least one proposal selects supplied RAG evidence when relevant.
- Planner and Reviewer complete or expose an explicit fallback reason.
- No full prompt or API key appears in logs.

If live execution is unavailable, record it as unverified rather than claiming success.

- [x] **Step 4: Update user-facing documentation**

Update the architecture wording from “five rule strategy agents” to the verified mode-aware description:

```text
Five role-specific LLM strategy agents independently generate structured candidate proposals in auto/on mode. Each role uses the same configured Qwen model with a distinct role prompt, while the original deterministic strategy implementation remains the per-role fallback and metric baseline.
```

Document:

- Seven-call maximum.
- `off` / `auto` / `on` semantics.
- Rule baseline plus bounded LLM adjustment.
- Per-agent generation Trace.
- Actual deterministic test count and live-test result.

- [x] **Step 5: Append the optimization log entry**

Add one dated round containing:

- Files changed.
- New components and data flow.
- Tests added and exact pass count.
- Live Qwen outcome or explicit reason it was not run.
- Known boundary: strategy agents consume shared upstream context but do not yet perform independent tool calls or LangGraph native fan-out.

- [x] **Step 6: Final verification checkpoint**

Run:

```powershell
pytest -q
python -m compileall . -q
```

Expected: both commands exit `0`. Review `OPTIMIZATION_LOG.md` and the interview document for stale claims that still describe all five agents as rule-only.
