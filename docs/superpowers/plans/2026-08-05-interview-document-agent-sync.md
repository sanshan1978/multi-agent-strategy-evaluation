# Interview Document Agent Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将实习面试文档整体同步到当前 5 路并行 LLM Strategy Agent 实现，并保证所有表述可由代码和测试支撑。

**Architecture:** 只修改面试文档和优化日志，不改变业务代码。更新按“实现入口与原理、面试问答与演示、全文校验与记录”三块推进，并使用文本扫描验证数字、边界和 Markdown 结构。

**Tech Stack:** Markdown、PowerShell 文本检查、pytest 已验证数据

## Global Constraints

- 只描述已经实现并验证的能力。
- 不把 `ThreadPoolExecutor` 并发说成 LangGraph 原生 fan-out/fan-in。
- 不把共享 RAG、Memory、Risk Context 说成每个 Agent 独立工具循环。
- 自动化测试数字保持为 141；Qwen live 结果保持为 5/5、0 fallback。
- 项目目录不是 Git 仓库，不执行提交或分支操作。

---

### Task 1: 补齐实现入口与技术原理

**Files:**
- Modify: `docs/实习面试项目介绍与问答.md`

**Interfaces:**
- Consumes: `agents.py` 的规则基线与 `llm_strategy_agents.py` 的 Profile、Pydantic Payload、并发 Runner
- Produces: 可用于代码讲解的模块入口和 Strategy Agent 技术专节

- [x] **Step 1:** 将核心模块表的策略 Agent 入口更新为 `agents.py` 与 `llm_strategy_agents.py`，区分规则基线和 LLM 生成职责。
- [x] **Step 2:** 在第 7 节增加“并行 LLM Strategy Agent”专节，说明输入、输出、并发、模式语义、fallback 和记录字段。
- [x] **Step 3:** 在第 9 节增加模型输出边界加固案例，覆盖 Action 清洗、confidence clamp、非有限数值拒绝和工作线程计时。
- [x] **Step 4:** 使用 `Select-String` 验证新增代码入口和技术关键词存在。

### Task 2: 补齐面试问答与演示

**Files:**
- Modify: `docs/实习面试项目介绍与问答.md`

**Interfaces:**
- Consumes: Task 1 的技术专节和当前 141 条测试结果
- Produces: 新版 Agent 高频问答、演示观察点和测试口径

- [x] **Step 1:** 增加同模型多 Agent、真实并发、单角色 fallback、严格模式诊断、调用次数与成本五类问答。
- [x] **Step 2:** 更新 Q47，加入真实重叠并发、非有限数值防护和 API/SSE 错误详情测试。
- [x] **Step 3:** 更新现场演示步骤，要求查看 `agent_generation` 中的 generation_mode、model、duration_ms、validation_status 和 fallback_reason。
- [x] **Step 4:** 保持“尚未完成”中的原生 fan-out/fan-in、独立工具循环和大规模 LLM Evaluation 边界。

### Task 3: 全文校验与优化记录

**Files:**
- Modify: `OPTIMIZATION_LOG.md`
- Verify: `docs/实习面试项目介绍与问答.md`

**Interfaces:**
- Consumes: Task 1、Task 2 的最终文档
- Produces: 一致性检查结果和可追溯改动记录

- [x] **Step 1:** 在优化日志新增“实习面试文档 Agent 内容整体同步”记录，列出更新范围和边界。
- [x] **Step 2:** 扫描旧测试数字、旧规则 Agent 表述、夸大能力和 API Key 模式。
- [x] **Step 3:** 检查 Markdown 代码围栏成对、Q 编号唯一递增、关键事实存在。
- [x] **Step 4:** 输出最终文件位置和语雀同步说明。
