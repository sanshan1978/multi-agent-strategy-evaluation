# 面试文档 LLM Strategy Agent 整体同步设计

## 目标

将 `docs/实习面试项目介绍与问答.md` 中仍停留在规则 Agent 版本或描述不足的部分，统一同步到当前“5 路并行 LLM Strategy Agent + 单角色 fallback”实现，确保项目介绍、代码讲解、技术问答、演示脚本和诚实边界相互一致。

## 修改范围

1. 修正核心模块入口：同时说明 `agents.py` 提供规则基线，`llm_strategy_agents.py` 提供角色 Profile、结构化输出、并发调度和 fallback。
2. 在核心技术实现中增加 Strategy Agent 专节，讲清角色隔离、Prompt 上下文、Pydantic 契约、指标有限调整、线程池并发、模式语义和可观测记录。
3. 在“真实遇到的问题”中补充模型输出边界加固，说明 Action 清洗、置信度截断、非有限数值拒绝和失败耗时修正。
4. 扩充面试问答，覆盖同模型多 Agent、并发证明、单角色 fallback、严格模式错误详情、调用次数与成本边界。
5. 更新演示脚本和测试说明，让现场能够展示 `agent_generation`，并准确说明 141 条测试新增覆盖内容。
6. 在 `OPTIMIZATION_LOG.md` 记录本次文档同步，不修改已经验证的 RAG、Planner、Qwen live 数据。

## 内容原则

- 只描述代码中已经实现和验证的能力。
- 不把线程池并发说成 LangGraph 原生 fan-out/fan-in。
- 不把共享上游工具上下文说成每个 Strategy Agent 独立执行工具循环。
- 不把一次 Qwen live smoke test 说成大规模 LLM Agent Evaluation。
- 保留项目用于虚构仿真和工程能力展示的定位。

## 验收标准

- 文档中的 Agent 代码入口包含 `llm_strategy_agents.py`。
- 核心技术实现有独立 Strategy Agent 专节。
- 面试问答覆盖实现机制、并发、fallback、错误诊断和成本。
- 所有测试数量统一为 141，不出现旧版 129。
- Markdown 标题层级和代码围栏完整，无 API Key 或夸大表述。
