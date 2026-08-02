# NovelCraft 本轮质量整改任务清单

更新时间：2026-08-02  
目标：把“生成质量、跨章连续性、去 AI 味、状态真实性和编辑器兜底”作为同一条产品链路一次性收口。编辑器只负责人工确认与最后局部修订，不承担首轮生成质量。

## 任务总览

| 编号 | 任务 | 本轮处理 | 当前状态 | 验收证据 |
|---|---|---|---|---|
| Q-01 | 单一正文链路 | 统一以 V7 Director 作为正文生成、审阅、重写和连续性门禁；V6 只接收通过/待重写结果并负责兼容书库、编辑器、导出 | 已接线 | `backend/app/workers/tasks.py`、`backend/app/v7/integration/v6_bridge.py` |
| Q-02 | 生成前质量 | 生成前注入 Novel Brain 真相状态、上一章结尾、交接契约、近期摘要、作者风格卡、已学习规则、剧情目标和场景节拍 | 可用 | `ContextAssembler`、`StoryDirector`、`GenerationEngine` |
| Q-03 | 场景级网文体验 | 生成提示要求每个场景完成“目标→阻碍→选择→代价/结果”，转折给出可见铺垫，高潮留下余波，章末以动作/发现/选择落钩 | 可用 | `backend/app/v7/generation/generation_engine.py` |
| Q-04 | 跨章连续性 | 使用上一章 transition contract、末尾原文和结构化状态；生成后校验人物、地点、时间、状态、开放线和下一章入口 | 可用 | `backend/app/v7/quality/continuity.py`、`backend/app/v7/integration/v6_bridge.py` |
| Q-05 | 真相状态 | 人物、世界、时间线、因果事件、伏笔、资源、关系和风格通过 Novel Brain/Truth Store 持久化，不依赖 LLM 自己记忆 | 可用 | `backend/app/v7/brain/`、`backend/app/v7/repositories/` |
| Q-06 | 规则自动学习 | 章节审阅结果、去 AI 味指标和人工保留/喜欢信号写入 Rule Learning；后续生成只注入已确认/高置信规则 | 已接线 | `backend/app/v7/quality/rule_learning.py`、`backend/app/main.py` |
| Q-07 | 33 维度审计 | Review Engine 保留 7 个宏观产品维度，同时执行 33 个细项审计；硬门禁维度不能被平均分掩盖 | 可用 | `backend/app/v7/quality/audit_dimensions.py`、`backend/app/v7/engines/review_engine.py` |
| Q-08 | 去 AI 味源头控制 | Prompt 不设置单个词或标点禁令，只控制高密度、连续重复、同构段落、均匀句长、总结腔和空泛说明 | 可用 | `backend/app/prompt_registry.py`、`backend/app/v7/generation/generation_engine.py` |
| Q-09 | 去 AI 味确定性审计 | 统计句长波动、段落开头重复、套话、破折号/省略号密度和重复短语；仅对整章分布风险拦截，不因一次正常标点直接拒绝 | 可用 | `backend/app/v7/quality/deai_metrics.py`、`backend/app/v7/integration/quality.py` |
| Q-10 | 去 AI 味保内容 | Provider 合并段落时只在句号/问号/感叹号边界重排，校验字符比例和段落下限；真实删文进入重试/失败，不静默落库 | 可用 | `backend/app/services/text_quality.py`、`backend/app/workers/tasks.py`、`backend/app/v7/generation/generation_engine.py` |
| Q-11 | 生成质量重试 | 章节草稿、润色、人文化在质量门不通过时获得具体反馈并重新调用真实 Provider；最多 3 轮，失败明确为待重写/失败 | 可用 | `StoryDirector._observe`、Bootstrap quality loop |
| Q-12 | 用户目标一致性 | 创作圣经必须明确写出用户目标总字数；若模型改成其他篇幅，规划节点重试，三轮仍失败则不放行 | 可用 | `bootstrap.plan_idea`、`_target_words_guard` |
| Q-13 | 失败状态真实化 | 运行状态以节点状态为准；失败、预算阻塞、Provider 失败、质量待重写不能显示为已完成；重试后立即刷新节点和运行状态 | 可用 | `Progress.tsx`、`WorkspaceDashboard.tsx`、`App.tsx` |
| Q-14 | Provider 失败可见 | 流式/非流式生成超时、Provider 错误、离线请求均显示明确错误或进入离线队列，不重复发起可能重复扣费的请求 | 已接线 | `App.tsx`、`ai_edit` |
| Q-15 | 编辑器预览优先 | AI 结果先进入原文/建议对比预览，用户确认后再更新草稿和创建版本；应用失败时保持原文和待确认建议 | 可用 | `App.tsx`、`Editor.tsx` |
| Q-16 | 编辑器最后兜底 | 整章操作使用产品字数和质量门；选区操作按选区比例，不用 2000 字硬门误伤短选区；失败不显示“完成” | 可用 | `backend/app/main.py`、`frontend/src/components/Editor.tsx` |
| Q-17 | 标题/简介/章节名 | 规划 Prompt 增加榜单口吻、反差/悬念、读者承诺和目标篇幅约束；前端统一清理重复书名书名号 | 已接线 | `bootstrap.plan_idea`、`titleDisplay.ts` |
| Q-18 | 排行榜中心 | 全站扫榜与按类型扫榜保留来源、时间、去重、样本稀疏提示、竞争/空位分析；跨平台分析采用并行部分成功，不因单平台超时拖垮全部 | 已接线 | `backend/app/api/v1/ranking.py`、`RankingCenter.tsx` |
| Q-19 | 目录导入/导出 | 目录文件可读取并预览后确认导入；TXT/MD 导出使用稳定下载节点，失败明确提示 | 可用 | `BookLibrary.tsx` |
| Q-20 | 审阅展示 | 结构化问题转换为可读中文，避免 `[object Object]`、原始 JSON 和空白审阅卡 | 可用 | `Review.tsx`、`Editor.tsx` |
| Q-21 | 回归与门禁 | 前端构建、前端单测、后端质量回归、差异检查、AI 真实性门禁和交付验证全部留证 | 可用 | 本轮交付记录；全量后端 878 passed / 138 skipped / 1 xpassed；前端 34 passed；构建通过 |
| Q-22 | V7 监控入口 | V7 无作品时也显示真实空态；有作品时显示总览、成本账本和 Prompt provenance；走查定位器与现行中文 UI 保持一致 | 可用 | `App.tsx`、`V7Dashboard.tsx`、生产走查脚本 |

## 质量门禁

正文进入 V6 书库前必须同时满足：

1. 总体质量分不低于 85。
2. 连续性、人物声音、剧情逻辑、节奏、文字质量、约束遵守等关键维度均不低于 85。
3. 33 维度审计中的硬门禁项不低于 85。
4. 去 AI 味风险不能命中高风险总分或高密度/连续重复标记。
5. 有上一章时必须有可验证的 transition contract；首章也必须产生可供下一章承接的结尾、摘要、状态变化和开放线。
6. 正文长度达到目标；人文化/润色不得低于原文安全比例，不能因段落换行丢失而误判，也不能借重排掩盖真实删文。
7. 任一门禁失败时，只能进入“质量待重写/待人工处理”，不能标记已完成或已入库。

## 本轮回归证据

以下命令必须在提交前执行并记录输出：

```text
cd backend && ./.venv/bin/pytest -q tests/test_text_quality.py tests/test_v6_quality_guards.py tests/test_quality_risks.py tests/test_story_revision_quality.py
cd frontend && npm run build && npm test -- --run
git diff --check
bash scripts/ai_development_gate.sh
```

## 不能由代码自证的外部验收

以下不是代码缺口，不能用确定性测试冒充完成：

- 真实 Provider Key、费用授权下的 20 章双轨/连续写作长跑。
- 两位独立人工评审的盲评覆盖、评分和分歧记录。
- “网文读者体验达到产品目标”的最终人工判断。

代码侧已经做到：Provider 缺失、超时、质量门失败和内容破坏都会显式失败；在真实环境具备凭据和评审人后，使用既有 `scripts/v6v7_20_chapter_quality.py --execute --confirm I_UNDERSTAND_REAL_API_COST_AND_DUAL_WRITE` 产生最终证据。

当前对外状态只能写为：代码整改可用，单一 V7 正文链路已接线，真实长跑与人工质量验收待外部条件满足。
