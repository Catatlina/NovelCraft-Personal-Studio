# V3 融合需求追踪（全文档 12 条）

> 来源：`docs/NovelCraft-V3-融合需求与开发文档.md` 第 13 章。状态四档：未开始 / 已接线 / 可用 / 已验收。
> 每条均按文档 §14 提交格式落地：真实 Provider 场景 + 自动化测试（纳入回归套件），禁止 mock / 空页面 / 只建字段不接 AI 流程。
> 决策（已与用户确认）：Repair Engine 局部修复**不新建版本分支、原地增量记录**；全量验收 = 回归全绿 + 真实 AI 全链（⑤⑦）+ 每 V3 功能真实 AI 场景。
> 2026-07-29 真实性复核：run `955d4719-8e21-4043-8a3e-2352c06c0ce2` 为 20/20 节点、22 条真实 AI 调用；扩展场景另验证认知/时间线/作者风格/场景导演。Repair Engine 仍缺预览后应用闭环，因此 12 项整体仍为**已接线**。
> 同提交工程门禁：`5c544ff` / Actions `30445384633` 的五项检查全绿。

## 第零阶段（前置验证）
- [ ] 现有防崩体系百万字量级验证（7层上下文装配 + 每10章巡检 + 卷级复盘门禁）—— 待做

## 第一阶段（提升生成质量）
| # | 功能 | 状态 | 挂载点 | 验收 |
|---|------|------|--------|------|
| ① | Chapter Function | **可用** | 细纲 Schema 加 function_type/chapter_goal/reader_expectation（必填，缺→打回重生成）；草稿提示强制围绕功能；Reviewer 七维增「节奏检测」维度（不阻塞门禁） | run `955d4719` 的细纲、Writer 输入和章 meta 均有真实证据；自动化回归通过 |
| ② | Novel DNA | **可用** | plan_idea 同一次调用产出 commercial_positioning/story_promise/forbidden_deviations（不增调用）；存为书 meta 顶层键 + novel_dna 嵌套；草稿提示注入 `$forbidden_deviations` 强约束；`_check_novel_dna_consistency` 自洽校验（红线与定位/承诺矛盾→fail，存 meta） | run `955d4719` 真实产出并持久化 DNA，Writer 编译指令含创作红线 |
| ③ | Story Arc 单层实体化 | **可用** | 故事弧 entity_type=story_arc（parent_id 挂书，旧书无弧优雅降级）；蓝图阶段新增 `generate_story_arc` 节点；装配器插 `arc_summary`；终审做弧线追踪 | run `955d4719` 的 `generate_story_arc` 和故事弧实体真实成功；提交 `391ef3b` CI 全绿 |
| ④ | 网文策略库 MVP | **可用** | strategy 表 + 3 个策略；Writer 按章序/功能匹配策略和 Skill 提示；Prompt Compiler 合并策略、DNA 红线和 Chapter Function | run `955d4719` Writer 请求含 246 字符编译指令，三层标签均真实存在；产品路径回归通过 |
| ⑤ | Repair Engine 三级版 | **已接线** | 失败证据分级为局部修复/整章重写/重新规划；审阅页调用统一 preview/apply API。预览签名、防篡改、`updated_at` 冲突门禁；用户确认前不改正文/细纲；局部替换保留 TipTap 结构，应用后仍进入待复审/待重写 | Repair 定向 15 passed、后端 781 passed、前端 14 passed/build、E2E 4 passed；浏览器负向失败不覆盖。正向真实 Provider 场景与同提交 CI 待完成 |

## 第二阶段（提升百万字能力）
| # | 功能 | 状态 | 挂载点 | 验收 |
|---|------|------|--------|------|
| ⑥ | 人物认知分层 | **可用** | `known_info JSONB` + 五层拆分、持久化、装配和认知穿帮提示；人物提取现强制至少一条分层认知事实；`get_states` 按 novel 隔离 | 真实 `extract_entities`：7 实体/15 认知事实，装配文本出现“认知分层”；契约回归通过 |
| ⑦ | 时间线真实锚点 | **可用** | 时间线锚点字段、真实提取、确定性年代检测、终审和巡检 | 真实 `extract_timeline` 产出并持久化 5 条事件；自动化回归通过 |
| ⑧ | 读者体验审核维度 | **可用** | Bootstrap 最终一致性强制返回五维读者体验并持久化；续写 `review_7dim` 同样消费，弱维只告警不伪造硬失败 | run `955d4719` 真实五维为 82/78/76/80/84，持久化平均 80 |
| ⑨ | Pacing Engine 可视化 | **可用** | 后端真库时间序列 + 鉴权端点 + Editor SVG 三线曲线 | run `955d4719` 的真实章节返回 1 个曲线点且包含读者体验；前端 12 tests/build 通过 |

## 第三阶段（护城河，依赖前两阶段数据）
| # | 功能 | 状态 | 挂载点 | 验收 |
|---|------|------|--------|------|
| ⑩ | Author Style Card 强化 | **可用** | 编辑器 diff/喜欢信号真实提交事务；反馈 API 自动调度 Learning Agent；卡片持久化后注入 ContextAssembler | 真库记录 1 条信号并重建卡片，装配文本出现作者风格层；事务/调度回归通过 |
| ⑪ | 场景层 Scene + Scene Director Agent | **可用** | scenes 表、真实 Provider、Celery/API、事务持久化、装配层和 Editor SceneBoard；轮询使用本次结果 | 真实 `scene_direct` 生成并持久化 5 场，装配文本出现分镜层；提交 `391ef3b` 已修复事务并 CI 全绿 |
| ⑫ | Prompt Compiler 通用引擎 | **可用** | compile_prompt/compile_generic_prompt 现由 Bootstrap Writer 产品路径实际调用，组装策略、DNA 与章功能 | run `955d4719` 的 ai_call 输入存在真实编译指令；产品路径回归通过 |

## 提交记录
- 2682f9d KI-007 修复（前序）
- （本批）① Chapter Function：gateway _BlueprintChapterOutlineItem 必填字段 + 提示扩展；tasks _check_chapter_function_pacing + 节奏检测维度；tests/test_chapter_function.py
- （本批）② Novel DNA：gateway _PlanIdeaOutput 加 commercial_positioning/story_promise/forbidden_deviations；prompt_registry plan_idea 提示+契约示例+草稿注入；tasks _check_novel_dna_consistency + plan_idea 持久化（顶层 meta 键 + novel_dna 嵌套）；tests/test_novel_dna.py
- （本批）③ Story Arc：gateway _GenerateStoryArcOutput（_StoryArcItem，status 默认 planning）；tasks 蓝图阶段加 generate_story_arc 节点 + _enrich_blueprint_context 注入 _volume_plan；persist 存 story_arc 实体；assembler 插 arc_summary 层；patrol_check 加弧完整性/进度校验；final_consistency_check 加 _check_story_arc_coverage（确定性偏移检测→warning）+ 弧线追踪维度；tests/test_story_arc.py 6 passed
- （本批）④ 网文策略库 MVP：Alembic 迁移 nc_v3_strategy（strategy 表）+ init_db 幂等建表与预置3策略（黄金三章/打脸策略/身份反转）；app/services/prompt_compiler.py（select_strategies/compile_strategy_directive/compile_prompt/skill_hints_for_strategies + _STRATEGY_SKILL_MAP 映射 generate_conflict/generate_hook 为中文技巧提示）；write_chapter_draft 模板加 $strategy_directive/$skill_hints 占位，节点注入匹配 directive+skill；覆盖不到优雅降级；tests/test_strategy_library.py 9 passed
- （本批）⑥ 人物认知分层：Alembic 迁移 nc_v3_entity_known_info（entity_states.known_info JSONB）；entity_tracker KNOWN_INFO_LAYERS + split_known_info 纯函数 5 层拆分；assembler _entity_states 渲染 5 层认知标签；review.ooc 提示扩 cognitive_leaks（认知穿帮并入 OOC，不增调用）；tests/test_cognition_layering.py 6 passed
- （本批）⑦ 时间线真实锚点：Alembic 迁移 nc_v3_timeline_anchor（timeline_events.real_world_anchor/anachronism_check）；timeline.py 纯函数 is_reality_based/parse_year_anchor/check_anachronisms/anchor_rule_for + ANACHRONISM_ERA_TABLE 产品年份表；extract_timeline 持久化锚点+自动规则；narrative.extract_timeline 提示扩可选锚点字段；final_consistency_check 加 timeline_anchor_check（现实向启用、warning 不阻断）；patrol_check 巡检年代错乱章节；tests/test_timeline_anchor.py 9 passed
- （本批）⑤ Repair Engine 三级版：_classify_repair_level（纯逻辑分级：剧情>逻辑>表达>文字优先级，映射 repair_local/rewrite/replan）；repair_local 节点（prompt+ _RepairLocalOutput 契约 + _apply_replacements 局部替换 + meta.repair_log 原地增量不建版本分支，符合§8.4）；replan_chapter 节点（prompt + _ReplanChapterOutput 契约 + meta.replan_log）；final_consistency_check 失败路径写 repair_recommendation（分级推荐，保留 needs_rewrite 兜底）；db.py task_types 加 repair_local/replan_chapter 路由；tests/test_repair_engine.py 10 passed
- （本批）⑧ 读者体验审核维度：gateway _ReaderExperience 可选契约（5 维 0-100，legacy 输出兼容）挂 _ReviewOutput.reader_experience；bootstrap.review_7dim 提示扩读者体验 5 维（期待/冲突/爽点/情绪变化/追读意愿，不计入 score）+ 示例与 fallback 同步；services/reader_experience.py 纯函数 normalize/summarize（<60 弱维→warning 纯 advisory）/issues 渲染；章审核节点持久化 meta.reader_experience + 弱维并入 review issues 不改 score；patrol_check 巡检弱体验章节计数；tests/test_reader_experience.py 11 passed
- （本批）⑨ Pacing Engine 可视化：services/pacing_series.py（build_pacing_series 纯函数聚合 + get_pacing_series 查询，关联 chapter_id 时间序列）；GET /novels/{id}/pacing-series 端点（novel member 鉴权）；前端 PacingCurve.tsx 纯 SVG 三线折线（节奏/读者体验/评分，无新依赖）挂 Editor 左栏；tests/test_pacing_series.py 5 passed + tsc 0 错 + vitest 12 passed
- （本批）⑩ Author Style Card 强化：Alembic 迁移 nc_v3_author_style（author_style_signals 信号表 + style_cards 卡表，UNIQUE project_id）；services/author_style.py 纯函数 normalize_signals/summarize_signals（keep_ratio/deletion_ratio/edit_preference 三档：aggressive_editor≥0.5/moderate/faithful_keeper，liked_phrases 2-gram 提取）/merge_style_card/learn_from_signals（复用 style_learn.learn_style + 信号摘要，顶层暴露 liked_phrases 供 assembler 注入）；POST /api/v1/author-style/{pid}/signals（记录编辑diff段）+ /like（标记喜欢）+ /learn（触发 celery run_author_style_learning 异步重建）+ /card（读卡）；assembler 第9层 author_style 注入生成上下文（project_id→style_cards，无数据降级空）；m3_tasks.run_author_style_learning 异步消费信号+知识库样本持久化 card；前端 Editor 工具栏「标记喜欢」按钮 + App saveChapter 时 fire-and-forget 采集 diff 信号；tests/test_author_style.py 9 passed

- （本批）⑪ 场景层 Scene + Scene Director：Alembic 迁移 nc_v3_scene_layer（scenes 表 chapter_id/project_id/scene_index/title/beat/goal/setting/pov/meta）；gateway 加 _ScenePlanOutput（scenes≥1）注册 scene_direct；prompt_registry 加 scene.direct 提示（章节级分镜：title/beat/goal/setting/pov，因果链+转折/高潮+钩子）+ fallback 同步；services/scene_director.py 纯函数 split_scenes（分隔线/空行确定性切分）+ normalize_scene（beat 非法降级发展）+ persist_scenes/get_scenes/direct_scenes（调用 gateway.complete 真实 Provider 落库）；celery run_scene_direction 异步（取章节 function + assembler arc/recent 摘要喂 Director）；端点 POST/GET /api/v1/chapters/{id}/scene-direct|/scenes（require_project_member 鉴权）；assembler 第9层 scene_plan 注入生成上下文（chapter_id 查 scenes）；前端 SceneBoard.tsx 折叠面板（生成分镜按钮 + 分镜列表）+ Editor 接线；tests/test_scene_director.py 7 passed

- （本批）⑫ Prompt Compiler 通用引擎：prompt_compiler.py 扩展 render_template（委托 prompt_registry.render_prompt 安全替 $var）+ compile_generic_prompt(base, layers, priorities) 按优先级排序泛用组装 + compile_prompt 保持兼容旧签名并增 extra_layers 通用层注入；tests/test_strategy_library.py +5 通用测试（空层/优先级排序/空值跳过/默认低优先/extra_layers）；V3 全套 93 passed + tsc 0 错 + vitest 12 passed
