# 通用写作方法论接入说明

## 来源

本次接入来源于用户提供的 `通用写作方法论-v1.0.0.zip`，系统实现版本为 `1.0.0`。源包包含正文生成方法、因果与连续性审查协议、章节生成提示词、独立审稿提示词、工作流 schema 和状态机说明。

系统没有把整份长文原样拼进每次 Prompt，而是将可执行部分编译为后端契约：

- `backend/app/v7/quality/writing_methodology.py`：唯一的机器规则与状态契约实现；
- `chapter_contract`：核心问题、可见兑现、代价/余波、下一必然压力；
- `causal_ledger`：事件、知情边界、为什么现在、代价、下一影响五列账本；
- `current_state` / `state_delta`：时间、地点、知识、物件、资源、关系的状态锚点；
- `external_evaluation`：外部检测结果必须绑定当前正文 SHA-256，不允许系统伪造分数。

## 已接入链路

1. `PlotEngine` 生成前要求输出章节契约、因果账本和状态变化。
2. `SceneDirector` 继承结构编辑结果；若账本缺列，正文生成质量标记为失败，不能作为可用章节。
3. `GenerationEngine` 将契约注入场景计划、正文生成和续写提示词，同时把工作流写入上下文与结果。
4. `ReviewEngine` 审查事件因果、知情边界、代价和下一影响，并继续使用 V7 的 33 项证据审阅作为主审阅链。
5. `StoryDirector` 在更新阶段保存工作流状态：`input_pending`、`causal_ready`、`drafted`、`causal_passed`、`external_pending`、`blocked` 等。
6. `POST /api/v1/chapters/{chapter_id}/external-evaluation` 登记真实外部评测结果；输入哈希不匹配时拒绝写入。

## 边界

这套方法论负责“生成前想清楚、写作中有依据、写完可追溯”。它不会用固定短句比例、感官比例、段落比例、错别字或批量删字来伪造人工感，也不会把外部检测分数当作系统内部推测。V7 的连续性硬门禁、质量审阅和人工审核仍然有效。
