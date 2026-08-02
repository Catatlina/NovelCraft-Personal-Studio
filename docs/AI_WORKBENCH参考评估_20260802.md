# ai-workbench 参考评估（2026-08-02）

## 结论

`/Users/genius/Workbuddy/2026-07-03-12-42-23/ai-workbench` 有可以借鉴的产品思路，但不能直接作为 NovelCraft 的质量实现。它更像一个通用内容工作流样板：有工作流状态、重试、Prompt CRUD 和基础的长文写作/去 AI Prompt；NovelCraft 当前的 V6/V7 运行时、跨章交接契约、事实修复、真实 Provider 门禁、Prompt hash 和成本账本更适合作为生产底座。

本轮实际采用的是“取设计意图、保留 NovelCraft 的证据门禁”原则：保留可验证的情绪目标、节奏钩子、分层去 AI 和读者体验字段；不复制其弱版本留痕、长度式自动评分、LLM fallback 或自动通过逻辑。

## 对照结果

| ai-workbench 资产 | 参考价值 | NovelCraft 处理 | 证据状态 |
|---|---|---|---|
| `backend/app/modules/novel_writing/prompts.py` 的 `novel-write` | 情绪先行、章节内小钩子、章末钩子、对白潜台词 | 已由 V7 场景计划、章节生成提示和跨章交接契约承接；继续补充到 V7 审稿证据 | 可用 |
| `novel-deslop` 的结构/句法/词语/网文四层去味 | 比单一“删套话”更接近实际去 AI | 已由 V6/V7 rule pre-clean + Provider-backed `final_humanize` 承接；事实、长度、段落保护优先 | 可用 |
| `novel-review` 的 expectation/conflict/payoff/emotion_shift/worth_continuing | 补足纯技术评分看不到的追读体验 | NovelCraft 已有 `reader_experience` 归一化、弱项告警和持久化；V7 审稿将要求同一结构化证据 | 已接线 |
| `workflow_engine.py` 的 `COLLECT→PROCESS→ANALYZE→GENERATE→PUBLISH` 与 retry | 长任务可观察、失败可重试 | 只借鉴状态机和失败显式化；生成链继续使用 V7 Director 的 plan/generate/review/rework/update，避免通用 PublishStep 代替质量门禁 | 可用 |
| `prompt_service.py` 的版本/回滚 | 提醒 Prompt 需要可运营 | 不直接复用：其版本是简单整数、无 rendered prompt/hash/执行账本，且无生产播种证据 | 未验收 |
| `workflow_steps.py` 的长度/章节数自动评级与自动批准 | 不足以证明小说质量 | 明确不采用；NovelCraft 只允许通过真实审稿、连续性/事实检查和 Provider-backed 人文化后写入 V6 | 可用 |

## 已落入 NovelCraft 的质量链

1. 章节生成上下文保留上一章尾部、上一章交接契约、人物/情节状态、约束和文风卡；V7→V6 的 `transition_contract` 保存下一章需要的尾部、事件、开放线索和禁止改动项。
2. 场景计划携带本章目的、冲突、节拍、情绪和章末钩子；章节正文必须在连续性硬门禁下生成，长度不足只能继续写，不能把短稿伪装成成功。
3. 去 AI 分成规则预清理与真实 Provider 的语义人文化定稿。定稿不改变事实、人物、因果、物品状态和对白信息，并检查长度和段落保留；Provider 不可用时失败，不回退成“看起来成功”。
4. V7 审稿保留 7 个硬质量维度，同时记录读者体验的五项证据：期待感、冲突感、爽点、情绪变化和追读意愿。读者体验弱项是告警，不能替代一致性和写作质量硬门禁。
5. V6/V7 共用 Provider transport、Prompt provenance 和 `ai_execution_ledger`，执行记录带 prompt hash、模型、token、费用、状态和幂等键。

## 不采用的部分及原因

- 不采用 ai-workbench 的 LLM fallback 作为生成成功：缺 Provider 时必须失败或进入待人工状态。
- 不采用按字数、段落数量或是否有结论的自动 A/B 评级：这无法证明上下章连贯，也无法证明去 AI 质量。
- 不把它的全局简单 Prompt 版本直接接入生产：NovelCraft 需要版本标签、模板 hash、精确渲染 Prompt、执行账本和数据库播种证据。
- 不把通用工作流 PublishStep 当成 V6/V7 合并验收：最终写入必须经过 V7 质量门禁和 V6 幂等桥接。

## 仍需外部证据的项目

- 真实 Provider 多章长跑：当前机器未发现有效 Provider 凭据，不能执行或伪造 20 章双轨结果。
- 人工盲评：需要真实生成样本、脱敏编号、评审表和人工评分，不能由自动测试替代。
- PromptVersionManager 生产播种：本地迁移与 8 条运行时 Prompt 已执行并验证幂等；生产数据库接口仍需真实连通证据。

## 复核入口

- 参考项目 Prompt：`/Users/genius/Workbuddy/2026-07-03-12-42-23/ai-workbench/backend/app/modules/novel_writing/prompts.py`
- 参考项目工作流：`/Users/genius/Workbuddy/2026-07-03-12-42-23/ai-workbench/backend/app/services/workflow_engine.py`
- NovelCraft V7 生成：`backend/app/v7/generation/generation_engine.py`
- NovelCraft V7 审稿：`backend/app/v7/engines/review_engine.py`
- NovelCraft V6/V7 桥接：`backend/app/v7/integration/v6_bridge.py`
- NovelCraft 运行时账本：`backend/app/services/ai_runtime.py`
