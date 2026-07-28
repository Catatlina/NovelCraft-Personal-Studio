# V3 融合需求追踪（全文档 12 条）

> 来源：`docs/NovelCraft-V3-融合需求与开发文档.md` 第 13 章。状态四档：未开始 / 已接线 / 可用 / 已验收。
> 每条均按文档 §14 提交格式落地：真实 Provider 场景 + 自动化测试（纳入回归套件），禁止 mock / 空页面 / 只建字段不接 AI 流程。
> 决策（已与用户确认）：Repair Engine 局部修复**不新建版本分支、原地增量记录**；全量验收 = 回归全绿 + 真实 AI 全链（⑤⑦）+ 每 V3 功能真实 AI 场景。

## 第零阶段（前置验证）
- [ ] 现有防崩体系百万字量级验证（7层上下文装配 + 每10章巡检 + 卷级复盘门禁）—— 待做

## 第一阶段（提升生成质量）
| # | 功能 | 状态 | 挂载点 | 验收 |
|---|------|------|--------|------|
| ① | Chapter Function | **已接线** | 细纲 Schema 加 function_type/chapter_goal/reader_expectation（必填，缺→打回重生成）；草稿提示强制围绕功能；Reviewer 七维增「节奏检测」维度（不阻塞门禁） | `tests/test_chapter_function.py` 5 passed；真实 AI 全链 ⑤⑦ 待全量验收 |
| ② | Novel DNA | **已接线** | plan_idea 同一次调用产出 commercial_positioning/story_promise/forbidden_deviations（不增调用）；存为书 meta 顶层键 + novel_dna 嵌套；草稿提示注入 `$forbidden_deviations` 强约束；`_check_novel_dna_consistency` 自洽校验（红线与定位/承诺矛盾→fail，存 meta） | `tests/test_novel_dna.py` 4 passed；真实 AI 全链 ⑤⑦ 待全量验收 |
| ③ | Story Arc 单层实体化 | **已接线** | 故事弧 entity_type=story_arc（parent_id 挂书，旧书无弧优雅降级）；蓝图阶段新增 `generate_story_arc` 节点（StoryArchitect 调度，非 Story Architect 直接调用）；7层装配插 `arc_summary` 层（优先级在 volume 与 recent 之间）；每10章巡检加弧完整性/进度校验；final_consistency_check 加 `_check_story_arc_coverage` 确定性偏移检测（章在弧区间内但参与者零交集→warning，不阻塞门禁），并入 Reviewer 七维「弧线追踪」维度 | `tests/test_story_arc.py` 6 passed；真实 AI 全链 ⑤⑦ 待全量验收 |
| ④ | 网文策略库 MVP | 未开始 | 新 strategy 表（非versioned）；Prompt Compiler 组装函数注入 Writer；Skill 仅 generate_conflict/generate_hook | 待做 |
| ⑤ | Repair Engine 三级版 | 未开始 | 句/段级局部修复 + 章级复用 + 打回规划；局部修复原地增量（不分支） | 待做 |

## 第二阶段（提升百万字能力）
| # | 功能 | 状态 | 挂载点 | 验收 |
|---|------|------|--------|------|
| ⑥ | 人物认知分层 | 未开始 | entity_state.known_info 拆 5 层 + 穿帮 OOC 检测并入现有 OOC | 待做 |
| ⑦ | 时间线真实锚点 | 未开始 | timeline_event 加 real_world_anchor/anachronism_check（现实向启用） | 待做 |
| ⑧ | 读者体验审核维度 | 未开始 | 并入七维评分（读 Chapter Function 序列） | 待做 |
| ⑨ | Pacing Engine 可视化 | 未开始 | 节奏可视化 | 待做 |

## 第三阶段（护城河，依赖前两阶段数据）
| # | 功能 | 状态 | 挂载点 | 验收 |
|---|------|------|--------|------|
| ⑩ | Author Style Card 强化 | 未开始 | 依赖编辑 diff 数据积累 | 待做 |
| ⑪ | 场景层 Scene + Scene Director Agent | 未开始 | 依赖 Arc 验证；第二阶段后 | 待做 |
| ⑫ | Prompt Compiler 通用引擎 | 未开始 | 依赖策略库效果数据 | 待做 |

## 提交记录
- 2682f9d KI-007 修复（前序）
- （本批）① Chapter Function：gateway _BlueprintChapterOutlineItem 必填字段 + 提示扩展；tasks _check_chapter_function_pacing + 节奏检测维度；tests/test_chapter_function.py
- （本批）② Novel DNA：gateway _PlanIdeaOutput 加 commercial_positioning/story_promise/forbidden_deviations；prompt_registry plan_idea 提示+契约示例+草稿注入；tasks _check_novel_dna_consistency + plan_idea 持久化（顶层 meta 键 + novel_dna 嵌套）；tests/test_novel_dna.py
- （本批）③ Story Arc：gateway _GenerateStoryArcOutput（_StoryArcItem，status 默认 planning）；tasks 蓝图阶段加 generate_story_arc 节点 + _enrich_blueprint_context 注入 _volume_plan；persist 存 story_arc 实体；assembler 插 arc_summary 层；patrol_check 加弧完整性/进度校验；final_consistency_check 加 _check_story_arc_coverage（确定性偏移检测→warning）+ 弧线追踪维度；tests/test_story_arc.py 6 passed
