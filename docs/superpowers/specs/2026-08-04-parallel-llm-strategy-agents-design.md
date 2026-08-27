# Parallel LLM Strategy Agents Design

**Date:** 2026-08-04  
**Status:** Approved approach, pending implementation-plan review  
**Project:** 面向复杂对抗场景的多智能体策略评估系统

## 1. Objective

Upgrade the five existing rule-based strategy agents into five independently invoked LLM strategy agents while preserving the existing deterministic agents as per-agent fallbacks.

The target request path is:

```text
RAG / Memory / Risk Context
          |
          v
Five parallel Qwen strategy-agent calls
          |
          v
Schema validation + bounded metric adjustment
          |
          v
Per-agent fallback when needed
          |
          v
Five StrategyProposal objects
          |
          v
Existing dialogue, Reviewer, scoring and audit
```

One complete request may make up to seven Qwen calls:

1. One LLM Planner call.
2. Five independent strategy-agent calls.
3. One Reviewer call.

## 2. Goals

- Give each strategy agent an independent role, prompt and model invocation.
- Make retrieved knowledge, memory and risk context influence proposal content directly.
- Keep the five proposal results structurally compatible with the existing scoring pipeline.
- Run the five model calls concurrently to control end-to-end latency.
- Isolate failures so one failed agent does not discard four successful proposals in `auto` mode.
- Preserve deterministic local-rule behavior for offline tests and fallback execution.
- Record enough structured trace data to explain how every proposal was produced.

## 3. Non-goals

- Do not deploy five different foundation models; all agents use the configured `qwen3.7-plus` model.
- Do not allow an LLM to invent arbitrary final scores without a deterministic baseline.
- Do not replace the current Reviewer, scoring, Decision Audit, MCP or RAG implementations.
- Do not implement LangGraph native fan-out/fan-in in this iteration.
- Do not give each strategy agent unrestricted tool-calling permissions in this iteration.
- Do not remove the existing rule agents.

## 4. Current State and Gap

The current `generate_proposals` node executes:

```python
proposals = [agent.propose(scene) for agent in self.agents]
```

Each `propose()` method uses fixed text and deterministic formulas. RAG and Memory source lists are attached only after proposal generation. Qwen currently participates in tool planning and final proposal review, but not in the generation of the five candidate strategies.

As a result, the project currently represents rule-based multi-agent strategy generation with LLM planning and reviewing. It does not yet represent five LLM-driven strategy agents.

## 5. Chosen Architecture

### 5.1 Components

Add a focused module named `llm_strategy_agents.py`, containing:

- `StrategyAgentProfile`: immutable role configuration.
- `LLMStrategyProposalPayload`: Pydantic model for untrusted model output.
- `StrategyAgentGenerationResult`: one agent's proposal plus execution metadata.
- `LLMStrategyAgent`: builds the role prompt, invokes the model and validates the response.
- `ParallelStrategyAgentRunner`: executes the five agents concurrently and applies mode-specific fallback behavior.

Keep these existing responsibilities unchanged:

- `agents.py`: deterministic proposal providers and metric baselines.
- `LLMCoordinator`: configured Qwen transport and common JSON extraction helpers.
- `DecisionEngine`: workflow orchestration.
- `GroundingBuilder`: maps selected knowledge titles to stable `rag-N` evidence IDs.
- Existing scoring and Reviewer stages: final comparison and ranking.

### 5.2 Role Profiles

Create one profile for each existing strategy:

| Agent | Primary concerns | Expected behavior |
| --- | --- | --- |
| 强攻 | speed, strength advantage, breakthrough window | direct and time-sensitive proposal |
| 迂回 | terrain, intelligence, mobility, isolation | indirect maneuver proposal |
| 防御 | risk, supply, civilian safety, resilience | defensive and counterattack proposal |
| 诱骗 | intelligence, deception, information asymmetry | deception and disruption proposal |
| 火力压制 | targeting confidence, supply, collateral risk | support and suppression proposal |

Profiles define identity and constraints in code. The model cannot change `agent_name` or `strategy_name`.

## 6. Agent Input Contract

Every strategy agent receives:

- Structured `BattlefieldScene` data.
- Its `StrategyAgentProfile`.
- The deterministic rule proposal for the same role as a metric baseline and fallback reference.
- Retrieved knowledge snippets with title, source, score and bounded content excerpt.
- Recalled memory cases with record ID and bounded summary.
- Structured risk context.
- The required JSON response schema and allowed metric names.

Context limits:

- Include only upstream TopK RAG and Memory results.
- Truncate individual evidence excerpts before prompt construction.
- Never include API keys, internal environment variables or raw exception stacks.
- Treat retrieved text as evidence, not as trusted instructions, to reduce prompt-injection risk.

## 7. Agent Output Contract

The model returns JSON equivalent to:

```json
{
  "summary": "方案摘要",
  "actions": ["行动一", "行动二"],
  "rationale": "结合场景和证据的推理依据",
  "used_knowledge_titles": ["已提供的知识标题"],
  "used_memory_ids": [12],
  "metric_adjustments": {
    "success_prob": 4.0,
    "resource_efficiency": 1.0,
    "risk_control": -2.0,
    "response_speed": 3.0,
    "intel_alignment": 2.0
  },
  "confidence": 0.78
}
```

Pydantic validation rules:

- `summary` and `rationale` must be non-empty and length-bounded.
- `actions` must contain 2 to 6 non-empty actions.
- Knowledge titles must be a subset of the titles supplied in the prompt.
- Memory IDs must be a subset of supplied memory IDs.
- Metric names must belong to the existing five-metric contract.
- Each metric adjustment is clamped to `[-10, 10]`.
- Confidence is clamped to `[0.2, 1.0]`.
- Unknown fields are rejected with Pydantic `extra="forbid"` so schema drift is visible and testable.

## 8. Score Ownership

The LLM does not own final metric scores.

For each role:

```text
rule metric baseline + validated LLM adjustment = proposal metric
```

Each result is clamped to `[0, 100]`.

This preserves:

- Comparable scales across agents.
- Existing evaluation and ranking behavior.
- Deterministic fallback values.
- A bounded influence from uncalibrated LLM judgments.

The LLM owns proposal wording, actions, rationale, selected evidence and bounded adjustments. The local scoring pipeline continues to own dynamic weights and final ranking.

## 9. Concurrency Model

The existing graph and API path are synchronous. Use a bounded `ThreadPoolExecutor` inside the `generate_proposals` node for this iteration.

Requirements:

- Default maximum workers: 5.
- Submit exactly one task per configured strategy agent.
- Use the configured model timeout for each network call.
- Collect results independently.
- Restore results to the canonical five-agent order after completion.
- Do not mutate shared `StrategyProposal` objects inside worker threads.
- Build each result independently, then merge on the orchestration thread.
- Shut down the executor on every path.

Add `MESSAGE_TALK_AGENT_MAX_WORKERS`, constrained to `1..5` with a default of `5`, so tests and constrained environments can use serial execution.

## 10. Mode and Fallback Semantics

### `llm_mode=off`

- Do not make strategy-agent model calls.
- Return all five existing rule proposals.
- Mark every generation record as `rule`.

### `llm_mode=auto`

- Invoke all five LLM strategy agents when a configured client is available.
- If one agent times out, returns invalid JSON or fails validation, use only that role's rule proposal.
- Preserve successful LLM proposals from other roles.
- If no API key is available, use all five rule proposals.
- Continue to the existing Reviewer; it may also fall back according to current behavior.

### `llm_mode=on`

- Require a configured model client.
- Require all five strategy agents to return valid proposals.
- If any strategy-agent call fails, raise an explicit aggregated generation error before dialogue and scoring.
- Do not silently mix rule and LLM proposals in strict mode.

Fallback is role-local in `auto` mode and request-fatal in `on` mode.

## 11. Validation and Repair Boundary

Perform safe normalization only:

- Extract a JSON object from model output.
- Validate types and required fields.
- Clamp numeric ranges.
- Remove evidence references that were not supplied.
- Normalize whitespace and discard empty actions.

Do not fabricate missing strategy content. If required content remains invalid after normalization, treat the agent call as failed and apply mode-specific fallback.

## 12. Trace and Observability

Add one structured generation record per strategy agent with:

- `agent_name`
- `strategy_name`
- `generation_mode`: `llm`, `rule`, or `rule-fallback`
- `model`
- `duration_ms`
- `validation_status`
- `fallback_reason`
- selected knowledge titles
- selected memory IDs
- bounded metric adjustments

The `generate_proposals` Decision Trace event summarizes:

- LLM success count.
- Rule fallback count.
- Total node duration.
- Maximum individual agent duration.
- Per-agent generation records.

Do not log full prompts, API keys or unrestricted knowledge content. The existing SSE stream exposes the node Trace after the parallel batch completes. Per-agent streaming is out of scope for this iteration.

## 13. Grounding Behavior

Unlike the current implementation, each LLM strategy agent selects only the knowledge titles and memory IDs actually used in its reasoning.

Populate:

- `proposal.knowledge_sources` from validated `used_knowledge_titles`.
- `proposal.memory_sources` from validated `used_memory_ids`.

The existing `GroundingBuilder` then maps selected knowledge titles to `rag-N` evidence IDs. Rule and fallback proposals retain the current behavior of attaching available source references so they remain auditable.

## 14. Compatibility

- Preserve the existing `StrategyProposal` required fields.
- Add an `AgentGenerationRecord` dataclass with defaults in `models.py`.
- Add `agent_generation_records` to `DecisionGraphState` and `DecisionResult`, defaulting to an empty list.
- Serialize the records under an additive `agent_generation` response field while also including their summary in Decision Trace.
- Keep old stored JSON readable because the new response field is additive and no old record deserialization requires it.
- Preserve the canonical order of the five agents.
- Preserve `llm_mode=off` output behavior as closely as possible.
- Keep existing FastAPI endpoints and request schemas unchanged.
- Keep existing Docker and Chroma configuration unchanged.

## 15. Testing Strategy

### Unit tests

- Each role builds a distinct system prompt.
- Valid JSON becomes a compatible `StrategyProposal`.
- Unknown evidence references are removed.
- Metric adjustments and confidence are clamped.
- Invalid JSON triggers a role-local fallback in `auto` mode.
- Invalid JSON fails the request in `on` mode.
- `off` mode performs zero model calls.
- Missing API key in `auto` mode performs zero model calls and returns rule proposals.
- Result order remains canonical even when futures finish out of order.
- One failed agent does not replace four successful agents in `auto` mode.

### Integration tests

- Fake coordinator returns five distinct role outputs.
- Decision Trace contains five generation records.
- Final ranking consumes bounded metrics and Reviewer bonus.
- RAG titles selected by an LLM agent appear in Grounding Evidence.
- SSE still emits valid progress, result, done and error events.
- Existing rule-mode tests continue to pass.

### Live verification

- Run a controlled Qwen case and confirm five strategy-agent calls plus Planner and Reviewer.
- Confirm proposal text differs by role and cites supplied context.
- Record latency and fallback count without exposing secrets.
- Live verification is separate from deterministic CI and may be skipped when credentials or network are unavailable.

## 16. Acceptance Criteria

The iteration is complete when:

1. In `auto` or `on` mode with Qwen configured, all five roles independently invoke the model.
2. Five calls execute concurrently with configurable maximum workers.
3. Each valid response passes Pydantic validation and produces a `StrategyProposal`.
4. Metrics remain based on deterministic baselines plus bounded adjustments.
5. In `auto` mode, one failed role falls back without losing successful roles.
6. In `on` mode, any failed role makes the request fail explicitly.
7. RAG and Memory references selected by each LLM agent are preserved for Grounding.
8. Trace identifies the generation mode, model, latency and fallback reason for all five roles.
9. Existing FastAPI contracts and rule-only operation remain compatible.
10. New and existing automated tests pass.
11. `OPTIMIZATION_LOG.md` documents the implementation and verification evidence.

## 17. Deferred Follow-up

After this iteration is stable, evaluate a separate LangGraph fan-out/fan-in refactor using reducer-based state. That follow-up should not be mixed into this implementation because the current mutable sequential graph state would require a broader workflow rewrite.
