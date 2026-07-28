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
| ④ | 网文策略库 MVP | **已接线** | 新 `strategy` 表（Alembic 迁移 nc_v3_strategy + init_db 幂等双保险）；预置3策略（黄金三章/打脸策略/身份反转）；`app/services/prompt_compiler.py`：`select_strategies`（按 seq/function_type 匹配）+ `compile_strategy_directive`（拼阶段节奏）+ `compile_prompt`（含 Novel DNA 红线/Chapter Function/技巧降级）；write_chapter_draft 节点注入 `$strategy_directive`+`$skill_hints`；Skill 层 `generate_conflict`/`generate_hook` 经 `_STRATEGY_SKILL_MAP` 编译成中文技巧提示；覆盖不到优雅降级（directive/skill 为空不阻塞生成） | `tests/test_strategy_library.py` 9 passed；真实 AI 全链 ⑤⑦ 待全量验收 |
| ⑤ | Repair Engine 三级版 | **已接线** | `_classify_repair_level`（纯逻辑分级：sentence/paragraph→repair_local，chapter→章级重写复用现有，plot→replan_chapter；按剧情>逻辑>表达>文字优先级）；`repair_local` 节点（prompt+契约 _RepairLocalOutput：replacements 列表，`_apply_replacements` 局部替换，存 meta.repair_log **原地增量不建版本分支**，符合§8.4）；`replan_chapter` 节点（prompt+契约 _ReplanChapterOutput：revised_outline+rationale，存 meta.replan_log）；final_consistency_check 失败路径写入 `repair_recommendation`（分级推荐，保留现有 needs_rewrite 兜底） | `tests/test_repair_engine.py` 10 passed；真实 AI 全链 ⑤⑦ 待全量验收 |

## 第二阶段（提升百万字能力）
| # | 功能 | 状态 | 挂载点 | 验收 |
|---|------|------|--------|------|
| ⑥ | 人物认知分层 | **已接线** | `entity_states` 加 `known_info JSONB` 列（Alembic 迁移 nc_v3_entity_known_info）；`entity_tracker.split_known_info` 纯函数拆 5 层（world_facts/reader_known/protagonist_known/character_known/misunderstandings，dict 可带 layer/misunderstood 标志，默认 world_facts）；`extract_and_store` 写入 known_info 列；assembler `_entity_states` 渲染 5 层认知标签（世界事实/读者已知/主角已知/该角色已知/该角色误解）注入上下文；`review.ooc` 提示扩 cognitive_leaks 规则（角色误用未知/误解信息→认知穿帮，并入现有 OOC 检测不加调用） | `tests/test_cognition_layering.py` 6 passed；真实 AI 全链 ⑤⑦ 待全量验收 |
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
- （本批）④ 网文策略库 MVP：Alembic 迁移 nc_v3_strategy（strategy 表）+ init_db 幂等建表与预置3策略（黄金三章/打脸策略/身份反转）；app/services/prompt_compiler.py（select_strategies/compile_strategy_directive/compile_prompt/skill_hints_for_strategies + _STRATEGY_SKILL_MAP 映射 generate_conflict/generate_hook 为中文技巧提示）；write_chapter_draft 模板加 $strategy_directive/$skill_hints 占位，节点注入匹配 directive+skill；覆盖不到优雅降级；tests/test_strategy_library.py 9 passed
- （本批）⑥ 人物认知分层：Alembic 迁移 nc_v3_entity_known_info（entity_states.known_info JSONB）；entity_tracker KNOWN_INFO_LAYERS + split_known_info 纯函数 5 层拆分；assembler _entity_states 渲染 5 层认知标签；review.ooc 提示扩 cognitive_leaks（认知穿帮并入 OOC，不增调用）；tests/test_cognition_layering.py 6 passed
- （本批）⑤ Repair Engine 三级版：_classify_repair_level（纯逻辑分级：剧情>逻辑>表达>文字优先级，映射 repair_local/rewrite/replan）；repair_local 节点（prompt+ _RepairLocalOutput 契约 + _apply_replacements 局部替换 + meta.repair_log 原地增量不建版本分支，符合§8.4）；replan_chapter 节点（prompt + _ReplanChapterOutput 契约 + meta.replan_log）；final_consistency_check 失败路径写 repair_recommendation（分级推荐，保留 needs_rewrite 兜底）；db.py task_types 加 repair_local/replan_chapter 路由；tests/test_repair_engine.py 10 passed
