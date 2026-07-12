# NovelCraft Personal Studio — 真实进度

<!-- delivery-claims: strict -->

> 更新：2026-07-11（审计修复轮）｜ 权威摘要 ｜ 状态遵循《23-AI开发边界与交付真实性规范》
>
> **治理说明**：此前版本宣称"20/20 任务全部完成、6/6 深度融合、8/8 整合、真实 Provider T3/T5 通过、真实源 7 天稳定运行、浏览器 E2E 验收通过"，均无《23》§6 要求的验收证据（commit/命令/日期/输出），且"7 天 T5"与文档同日更新在时间上不可能成立。按《23》§8 全部降级为证据可查的状态；重建证据台账前不得恢复 ✅。外部审计报告（2026-07-11）的 §三/P1-6 亦指认了同一问题。

## 当前主线 (main)

| 能力 | 状态 | 已有证据 | 尚未覆盖 |
|---|---|---|---|
| 榜单采集 adapter | 🧪 待验收 | 纵横官方页真实采集 T3；番茄/起点失败显式化；导入/校验/置信度门禁有真库测试 | 番茄 OCR 与起点用户会话复验；真实源长周期 T5 |
| 榜单中心 | 🧪 待验收 | 扫榜、快照、分析、选题、成书前后端入口；导入与元数据校验 UI | 真实 AI 分析 T3、完整 E2E |
| 原创市场选题 | 🧪 待验收 | Gateway、严格 Schema、防注入、失败 `pending_provider` 契约测试 | 真实 Provider T3 输出证据 |
| 扫榜自动建书 | 🧪 待验收 | 幂等键建书、来源血缘、跳过人工选名 | 真实 Provider 批次成功路径 |
| 连续章节流水线 | 🧪 待验收 | 严格 Schema、章节幂等键、连续性风险报告、批次 `pending_provider`/resume 断点续跑；浏览器实测失败→恢复链与导出正文 | 真实 Provider 多章样本与批次成功路径 |
| 统一书库 | 🧪 待验收 | 书库 API/页面、检索/筛选/排序、目录导入（权限+seq+幂等落库）、导出 TXT/MD | 完整 E2E 验收 |
| 灵感 Bootstrap | 🚧 部分完成 | 灵感→书名→设定→第一章→审核基础链 | 真实 Provider 质量验收 |
| 热点自媒体 | 🚧 部分完成 | 知乎/微博采集器、Dashboard、社媒生成基础 | 去重/趋势/时效评分；可恢复工作流 |
| 长篇一致性 | 🚧 部分完成 | 上下文/摘要/实体/伏笔/时间线组件；伏笔与矛盾检查已按真实 schema 重写并有真库回归测试 | 百章压力、写后 reconcile、卷级门禁 |
| 发布中心 | 🚧 部分完成 | 平台账号 Fernet 加密落库（platform_accounts 启用）、发布状态机、敏感词前后端检查、发布记录 | 真实平台发布回执、数据回流、全自动 worker 调度 |

## 八上游项目融合

| 项目 | 状态 | 真实边界 |
|---|---|---|
| oh-story-claudecode | 🚧 部分完成 | 7 个上游 Skill 与许可证已保存；PromptSpec/golden cases 接入证据不完整 |
| denova | 🚧 部分完成 | run/node/SSE 基础与部分 WorkflowPlan/事件账本代码；未见完整行为对照测试 |
| show-me-the-story | 🚧 部分完成 | 伏笔、上下文和审核组件；章节事实事务链证据不完整 |
| AI_NovelGenerator | 🚧 部分完成 | 目录解析、通用审核与部分记忆组件；百章验收无证据 |
| AI-auto-generates | 🚧 部分完成 | 批量生成、拆书、Prompt 基础与章节目录导入落库 |
| harnessNovel | 🧱 骨架 | 阶段规划函数；分层规划/合理性审计/humanize 无验收证据 |
| BrowserAct (MIT) | 🧱 骨架 | 仅保留合规部分（用户已登录会话半自动发布包装）；anti-bot 能力按《25》不予融合、已删除 |
| insprira (AGPL 洁净室) | 🧱 骨架 | 账号追踪/诊断、违禁词检测独立实现，有 API/迁移/权限隔离；真实平台数据验收无证据 |

## 验证基线（2026-07-12 实测）

- 后端测试：**417 passed，4 skipped**（真实 Postgres；默认 AI 路径为 mock；真实 Provider/本地语义模型用例按环境显式启用）。
- 前端：`tsc --noEmit` + `vite build` 通过。
- Alembic：单头 `nc_audit_workflow_scope`；本地库 upgrade→downgrade→upgrade 往返通过。
- 浏览器实测（本轮）：审阅页时间线/人物弧线渲染真实数据；设置页数据统计为真实计数（AI 调用/内容数/pg_database_size）；书库批次失败→`pending_provider` 原因透传→恢复链路。
- **真实 Provider T3（2026-07-12，deepseek-chat）**：扫榜导入 20 条→市场分析（4 信号+3 原创候选，候选与源榜单零重合）→建书→策划全链 n3~n8（简介/世界观/人物/大纲/第一章 1028 字/七维审核 75 分含 1 次真实返工）→run succeeded→第二章 15s 生成（实体 7 条、时间线 6 条真实抽取、连续性 clean）→导出含真实正文。11 次调用 7924 tokens ≈¥0.016，全部记录于 ai_calls。真实链暴露并修复 2 个 mock 测不出的缺陷：①OUTPUT_CONTRACTS 章节示例 2 段与 Schema ≥3 冲突（模型照抄示例必失败）；②审核低分返工路径 UnboundLocalError（mock 恒 84 分从未触达）。验收测试固化于 `test_real_provider_t3.py`（无 key 自动 skip；CI 配 `DEEPSEEK_API_KEY` secret 即跑）。
- **浏览器自动化 E2E（P0-2，2026-07-12 落地）**：Playwright 脚手架（`frontend/playwright.config.ts` 双 webServer：uvicorn:8100 + vite:5273 代理），主链用例①注册→CSV 导入→快照落库→刷新持久→书库空态（无 AI 确定性，本地 2.2s passed）；用例②AI 分析→原创选题→建书→书库可见（protected，带 key 本地 16.1s passed / 无 key skipped）；CI 新增 e2e job（postgres+redis 服务、失败上传 trace 报告）。**首条 T4 自动化验收达成。**
- T5 长周期运行：仍无证据，未验收。

## 审计对照（外部审计报告 2026-07-11）

- 已修复（`efba333`）：B1 JWT 生产强校验、B2 管理员绕过收口、B4 裸 fetch 清除、P0-1 DB.close 改 rollback、P0-2 SSE 真换行、P1-4 死组件接线。
- 已修复（本轮）：B3 发布凭据 Fernet 加密落库（`platform_accounts` 启用，响应不回显凭据）；P0-3 compose api/worker 依赖 migrate 完成；P1-1 修复 3 条静默失败索引（错误列名，原迁移 `except: pass` 吞错）；Redis appendonly + 持久卷（更正：`7053a07` 提交信息声称 "Redis persistence" 但未实际配置，属《23》§4 虚假上报，本轮补齐）；F5 设置页假统计→真实 `/stats/overview`；F7 审阅页恒空时间线/弧线→真实 `/novels/{id}/narrative`；F8 敏感词前端空函数→真实 `/contents/{id}/check-sensitive` 并接入发布前置检查；F12 DagEditor 空 project_id→真实项目 ID 且缺失时拒绝保存。
- 已修复（第二轮，对照审计全量版 §六）：多轮审核/跨模型审计/Prompt 矩阵此前用字符串长度公式伪造评分并宣称"ready"，现真实经 Gateway 调用、Provider 不可用逐项 `pending_provider`，端点补 `project_id` 成员校验；热点采集 `except: continue` 静默空成功改为逐源状态+全失败 502；AgentConsole 硬编码"模拟"数据改为 `/agents/status` 真实 run_nodes 聚合；Collaboration 页面调用不存在的路径（必 404）改为真实 `/collaboration/*`；`/admin/workflows/{name}/execute` 此前无视工作流名一律跑 bootstrap 且 `project_id=''` 必然崩溃，改为权限校验+仅 bootstrap 可执行+其余显式 501；AI 编辑补 `ai_edit` 版本分支（C5-03）；C5-05 自动保存 7 天保留 beat 任务（保留每实体最近 10 份，语义分支永不清理）；assembler 知识层此前按无人写入的列过滤永远为空，改为按小说前提走 Knowledge Hub 检索。
- 已修复（第三轮，代码/文档/功能契约对账）：工作流保存请求原本必 422 且代码引用不存在的 `workflows.project_id/config`，现新增项目作用域迁移并统一使用 `definition`；系统 Bootstrap 只读，自定义 DAG 明确为设计稿、未接执行器返回 501；清除预算/日报/翻译四组重复路由及其中的跨项目翻译风险；设置页知识导入/导出与预算、知识检索、热点响应、Fanout 响应、多平台发布均对齐真实 API；短篇输入真实落库；Fanout Provider 失败不再复制原文冒充改写成功。
- 已修复（第四轮，按《27-全仓库审计报告》路线图阶段 0）：P1-A 迁移回滚断裂——性能索引 downgrade 移除 CONCURRENTLY，干净库 upgrade→downgrade base→upgrade 三段实测通过，并加全迁移源码契约测试；P1-B schema 快照契约测试（12 张核心表必需列钉死，防列名漂移复发）；P1-G 交付门禁升级为证据绑定校验（✅/已交付行必须含测试/commit/文件/T级标记，含负例测试）；P1-D 不可信外部文本统一清洗 `sanitize_untrusted`（接入 assembler 知识召回与热点晨报入模路径）；P1-E 备份 pg_dump 每日 sidecar + 7 份保留 + 全服务日志轮转（compose，YAML 校验通过）；P2 清理：PublishPage 死组件删除、`store_ranking_snapshot` 吞错死函数及其 T0 存在性断言删除、bundle 分包（主 chunk 702KB→281KB，消除 >500KB 警告）、版本统一（app `2.2.0` 对齐需求基线 V2.2，README 刷新）。**396 tests 全绿**。
- 已修复（第五轮，本轮审查）：纯文本编辑增加 DeepSeek SSE、完成后统一写 ai_calls/版本；流式鉴权支持 token 刷新，预算与 Provider 错误分流，非 DeepSeek 路由安全回退普通网关；Embedding 增加 remote/local/hash 三层适配、来源标记和项目重建，远端部分/非法响应回退 hash，不同后端向量禁止混算；Sentry/Prometheus 可选接线，巡检增加队列积压和成本日报。代码验证 417 passed、前端 build；真实流式 Provider、local semantic 和 Sentry 送达仍未作为验收证据。
- 全面复核（2026-07-12 第二轮，@068a45d）：PR#4 加固复核通过（流式 PENDING_BUDGET 语义/非 deepseek 显式拒绝/embedding 数量与有限性校验/检索按 provenance 过滤）；T5 提交内的一致性组件修复复核通过——entity/summarizer/timeline 此前把 AI 调用记账到 `SELECT id FROM projects LIMIT 1` 的**任意项目**（跨项目成本/预算污染），已改为按 content 归属项目；伏笔抽取 `hint_chapter` 字段对齐 prompt 契约；章节富化失败不再阻断落库与审核门禁。新增实测验收：**流式端到端真实 Provider 通过**（HTTP SSE 经 8100 API，逐字增量帧+done 帧，DeepSeek 真实调用）；**local 语义质量验收通过**（EMBEDDING_SEMANTIC_TEST=1，bge-small-zh 真实模型："地底嗡鸣"≈"深渊低语"≫无关文本，余弦差 >0.1，本机含首次模型下载 34s 完成 8/8）。
- 仍开放：B4 Nginx 无 TLS（需域名/证书决策）；流式浏览器端验收；remote embedding 质量验收（需 embedding API key）与全库重建演练；数据回流/ROI 真实数据；Sentry 与告警实测送达（需 DSN/Telegram env）；发布真实平台回执与 auto_publish 调度；`workers/tasks.py` 拆分；Agent 注册表仍为声明式（无独立执行体）；task/日级预算分级；T5 百章长跑进行中（完成后补证据）。

## 下一顺序

以《24-AI开发任务列表》为准：优先补真实 Provider T3 证据（解锁全部"待验收"），再做 E2E 脚手架与 T4 用例，随后按序推进 HM/PUB/SEA。任何状态回升必须绑定同一提交中的验收证据。
