# 降级与恢复知识

tags: degradation recovery embedding vector_store llm trace failure

## Embedding Service Degradation

Embedding 服务超时或限流时，严格索引任务应停止并保留失败批次，不允许用不同维度或不同模型静默写入同一 Collection。在线查询可按配置降级到稀疏检索，并明确标注 Dense Retrieval 不可用。恢复后需要校验模型和维度。

## Vector Store Unavailable Fallback

Chroma 不可用时，系统健康检查应报告依赖失败。若允许降级，查询只能使用当前内存中的稀疏索引，并在响应 Trace 中写入降级原因；不得伪造向量结果。恢复连接后先执行 heartbeat 和 Collection 元数据校验。

## LLM Planner Timeout Recovery

LLM Planner 超时时，调度器应在有限重试预算内使用同一幂等请求标识重试。预算耗尽后转入规则化最小安全计划，而不是无限等待或重复调用工具。评估记录尝试次数、累计延迟和降级计划来源。

## Partial Agent Failure Isolation

单个智能体异常时，系统应冻结其任务与工具锁，避免失败状态扩散到共享黑板。协调器根据任务可迁移性决定重新分配、等待恢复或终止相关分支。指标包括故障隔离时间、受影响任务数量和恢复成功率。

## Trace Storage Failure Buffering

Trace 存储短时不可用时，关键决策事件应写入有界内存缓冲并附加序列号。缓冲接近上限时优先保留安全、工具调用和终止事件，同时触发健康告警。恢复后按序补写并检测重复事件。
