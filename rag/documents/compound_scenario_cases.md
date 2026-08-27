# 复合场景案例知识

tags: compound_case urban mountain plain communication recovery multi_agent

## Urban Low Intel Evacuation Case

虚构城市疏散场景同时具备人员密集和情报不足条件。系统先启用保护区硬约束，再分配多源侦察确认通道状态；只有满足最低置信度的路线才能进入协调执行。评估联合检查人员风险、证据新鲜度和疏散通道可用率。

## Mountain Supply Communication Case

山地场景中补给不足且通信间歇中断时，智能体应缩小任务范围，保留安全储备，并在授权边界内自治维护观察点。重新连接后通过版本同步解决状态差异。评价包括储备余量、失联时间和状态收敛速度。

## Plain Urgent Deception Case

平原高时效任务出现疑似诱导信号时，系统不能因为时间紧迫而跳过一致性检查。应使用低成本验证任务快速判断，并只执行可撤销的短阶段计划。关键指标是首个动作延迟、误导资源投入和异常确认时间。

## Multi Agent Sensor Conflict Case

多个侦察智能体提交相互冲突的传感器结论时，协调器先检查证据独立性和新鲜度，再分配补充观测任务。共享黑板只发布带版本的临时结论，禁止未确认信息触发高风险工具。评估冲突解决时间和错误共识率。

## Long Duration Recovery Case

长时间运行中若先后出现 Embedding 限流、单智能体失败和 Trace 存储中断，系统应分别降级稠密检索、隔离失败角色并缓存关键事件。恢复顺序遵循依赖健康检查、数据一致性校验和任务重新分配，避免一次性恢复导致状态震荡。
