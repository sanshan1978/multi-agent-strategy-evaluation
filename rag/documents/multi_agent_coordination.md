# 多智能体协作知识

tags: multi_agent coordination role handoff blackboard consensus conflict

## Role Based Task Decomposition

复杂目标应根据能力边界拆分为感知、规划、执行、校验和安全监督等角色任务。每个子任务必须声明输入、输出、负责人和完成条件，避免多个智能体无边界地重复工作。评估包括职责覆盖率、重复任务比例和依赖等待时间。

## Scout Support Agent Handoff

侦察智能体向支援智能体移交任务时，需要同时传递目标状态、证据来源、置信度、有效期和未解决风险。接收方必须确认关键字段后才能开始执行。Trace 中应关联交接前后的任务 ID，便于审计信息是否丢失。

## Shared Blackboard Coordination

共享黑板用于发布任务状态、证据和资源占用，但写入必须使用版本控制与结构化 Schema。智能体只订阅与自身职责相关的事件，避免所有变化触发全体重规划。衡量指标包括事件处理延迟、重复消费和状态一致性。

## Parallel Plan Conflict Detection

多个计划并行执行前，系统应检查资源、空间、时间窗口和工具锁是否冲突。发现冲突后，根据任务价值和安全等级进行排序或重新分配，而不是让执行阶段自行竞争。评估记录预执行发现率和冲突导致的回滚次数。

## Consensus Timeout Fallback

协作决策不能无限等待所有智能体达成一致。系统应设置共识截止时间，在超时后根据最低安全方案、已有多数意见和关键角色否决权进入可解释的降级决策。Trace 必须记录缺席角色、超时长度和降级依据。
