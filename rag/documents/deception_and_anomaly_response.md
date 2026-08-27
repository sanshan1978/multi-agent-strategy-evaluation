# 欺骗识别与异常处置知识

tags: deception anomaly adversarial validation quarantine drift

## Deceptive Signal Consistency Check

疑似欺骗信号应与空间关系、时间连续性和多源观测进行一致性检查。单次高置信信号不能直接覆盖长期稳定证据；无法解释的突变需要进入待验证状态。评估记录异常分数、独立验证数量和误报率。

## False Target Exposure Control

系统怀疑目标为虚假诱导时，应限制资源投入并分配低成本验证任务，避免高价值智能体被单一线索持续牵引。验证完成前只允许可撤销动作。Trace 中要展示怀疑原因、验证预算和目标状态变化。

## Anomalous Tool Output Quarantine

工具返回格式合法但数值异常、来源未知或与上下文冲突时，输出必须先进入隔离区。隔离数据不能写入共享记忆或触发高影响节点，只有通过 Schema、范围和交叉证据校验后才能释放。指标包括隔离命中率和污染阻断数。

## Adversarial Prompt Injection Defense

知识文档和工具结果中的指令性文本不得覆盖系统策略或工具权限。系统应区分数据与控制指令，拒绝要求泄露密钥、修改安全规则或绕过审批的内容。审计记录需要保留触发模式、来源文档和阻断动作。

## Behavior Drift Detection

智能体行为与基准策略长期偏离时，应通过动作分布、工具调用频率和风险评分变化识别漂移。检测到持续漂移后，系统冻结高风险权限并转入回放分析。评价关注检测延迟、误报率和恢复后的一致性。
