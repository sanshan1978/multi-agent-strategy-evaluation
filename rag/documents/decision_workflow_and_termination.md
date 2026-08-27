# 决策流程与终止条件知识

tags: decision workflow planning execution termination rollback evidence

## Evidence First Planning Gate

规划开始前必须检查目标、约束、资源和关键证据是否齐全。缺失信息被转换为待办侦察任务，无法满足最低证据要求时不生成高影响执行计划。门控 Trace 包含缺失字段、证据置信度和允许继续的规则。

## Plan Execute Observe Loop

决策图采用规划、执行、观察和更新循环。每轮只执行可验证的一组动作，随后比较预期状态与实际状态，再决定继续、重规划或终止。循环次数、状态差异和节点耗时都需要写入 Trace。

## Conditional Branch Replanning

当观测命中预定义分支条件时，系统应从最近有效状态重新规划，而不是从头清空全部上下文。分支条件必须结构化、可测试并带有优先级。评估记录触发条件、保留状态和新旧计划差异。

## Termination Condition Validation

终止条件必须同时检查目标状态、安全状态和未完成副作用。只达到表面目标但仍存在高风险待处理项时，流程不能标记成功。系统应区分成功终止、安全中止、超时终止和失败终止。

## Rollback Checkpoint Policy

执行不可逆步骤前应建立包含状态、资源占用和外部工具结果的回滚检查点。回滚只能恢复已声明为可恢复的状态，不能假装撤销外部不可逆影响。审计输出包括检查点版本、恢复范围和未恢复项。
