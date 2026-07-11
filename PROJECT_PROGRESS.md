# NovelCraft Personal Studio — 真实进度

<!-- delivery-claims: strict -->

> 更新：2026-07-11 ｜ 权威摘要 ｜ 功能代码基线 `2da8975` ｜ 状态遵循《23-AI开发边界与交付真实性规范》
>
> 旧版百分比、“232/256 已完成”和六项目“全部融合”结论已废止。下面只报告有代码证据的交付边界。

## 当前主线

| 能力 | 状态 | 已有证据 | 尚未覆盖 |
|---|---|---|---|
| 榜单采集 adapter | 🧪 待验收 | 纵横官方页连续3次各20条，去重20/20、空标题0；番茄/起点失败显式化 | 浏览器T3验收、真实源7天T5；番茄旧API 404、起点反爬仍不可用 |
| 榜单专用数据模型 | 🧪 待验收 | 增加外部ID、去重键、抓取时间、来源失败计数和重放血缘；迁移往返通过 | 浏览器端完整验收 |
| 榜单中心 | 🧪 待验收 | 扫榜、快照、分析、选题、成书前后端入口 | 浏览器 E2E、真实 AI 分析 |
| 原创市场选题 | 🧪 待验收 | 已接 Gateway、严格输出 Schema、输入防注入、候选标题原创边界、失败 `pending_provider` | 缺真实 Provider T3 结果与浏览器验收；原创检查仅为风险辅助，不是版权结论 |
| 扫榜自动建书 | 🧪 待验收 | 选题创建 `contents(type=novel)`，记录来源并跳过人工选书名节点 | 真实 Provider 整书批次成功路径、T4 E2E |
| 连续章节流水线 | 🧪 待验收 | 严格输出 Schema、章节级幂等键、连续性风险报告、章节目录真实落库、七维审核→低分改写→再次审核门禁、批次质量计数与断点恢复、书库入口（续写/批量/恢复/导出） | 真实 Provider 多章样本、审核返工与批次成功路径浏览器 E2E；批次槽位级崩溃恢复仍需加强 |
| 统一书库 | 🧪 待验收 | 独立书库 API/页面，展示小说来源与状态 | 分页、检索、全部生成入口统一入库测试 |
| 灵感 Bootstrap | 🚧 部分完成 | 灵感→书名→设定→第一章→审核基础链 | 不是产品主入口；真实 Provider 质量验收不足 |
| 热点自媒体 | 🚧 部分完成 | 热点采集、Dashboard、社媒生成基础 | 热点→多平台稿→入库/发布的可恢复工作流 |
| 长篇一致性 | 🚧 部分完成 | 上下文、摘要、实体、伏笔、时间线组件 | 百章压力、写后 reconcile、卷级门禁 |

## 八项目融合

| 项目 | 状态 | 真实边界 |
|---|---|---|
| oh-story-claudecode | 🚧 部分完成 | 已保存 7 个上游 Skill 与许可证；尚未完成 33 PromptSpec、Schema、golden cases 和工作流接入 |
| denova | 🚧 部分完成 | 有 run/node/SSE 基础；缺完整 WorkflowPlan、事件账本、mutation、post-run verifier |
| show-me-the-story | 🚧 部分完成 | 有伏笔、上下文和审核组件；章节事实事务链未贯通 |
| AI_NovelGenerator | 🧱 骨架 | 有目录解析和通用审核；百章记忆、六类一致性、写前检索/写后合并未验收 |
| AI-auto-generates | 🧱 骨架 | 有批量生成、拆书和 Prompt 基础；缺完整拆书工作台、快捷词条、思维导图 |
| harnessNovel | 🧱 骨架 | 有阶段规划函数；分层 AI 规划、自适应窗口、合理性审计、知识合并和 humanize 未实现 |
| BrowserAct (MIT) | 🧱 骨架 | 仅保留合规部分：CLI 半自动发布包装（用户已登录会话）。上游 stealth-extract/anti-bot 能力按《25》合规边界不予融合，曾引入的抓取函数与 `/scrape/browseract` 端点已删除；CLI 未安装时显式 `unavailable`；无浏览器端验收 |
| insprira (AGPL 洁净室) | 🧱 骨架 | 账号追踪/诊断、违禁词检测、Skill 中心为独立实现，已有 API、迁移和项目权限隔离；外部拉取失败显式 `unavailable`；无前端入口、无真实平台数据验收 |

## 验证基线

- 仓库同步（2026-07-11）：本地 `agent/complete-core-gaps` 与 `origin/agent/complete-core-gaps` 为 `0/0`，不存在未拉取或未推送代码；该分支相对 `origin/main` 为 `45/0`，功能仍在 Draft PR #1，尚未合并到 main。
- 远端既有 CI：154 项后端测试通过，前端构建通过；其中包含较多 T0/T1 存在性测试，不能代表核心链 E2E。
- 当前验证（2026-07-11）：Alembic 单头 `nc_sc004_review_gate`，干净库 upgrade→单步 downgrade→upgrade 往返通过；宿主机后端 **259 passed**、前端 `tsc -b && vite build` 通过。纵横真实采集/持久化已有后端 T3；市场分析和章级审核仍缺真实 Provider T3，因此保持 `🧪`。
- 已知修复（2026-07-11）：novel 导出对 doc 格式章节输出空正文（已改为遍历 `content[]`）；`complete_api.py` 资源端点补齐项目成员校验；伏笔到期检查查询不存在的 `target_chapter` 列、跨章矛盾检查查询不存在的 `character_name/event_time` 列（真库从未生效，已按真实 schema 重写并补真库回归测试）。
- 已知修复（2026-07-11）：`POST /novels/{id}/import-chapters` 已从“只解析不落库”改为项目权限校验、连续 seq 真实落库、标题幂等去重、已有章节后追加和事务失败回滚；仍缺前端预览/确认入口。
- 环境提示：docker 前端容器镜像依赖过旧（缺 Tiptap），只挂载 `src` 导致一直在供旧 UI，需 `docker compose build frontend` 重建。
- PR：`agent/complete-core-gaps` → `main`（Draft）。

## 下一顺序

以《24-AI开发任务列表》为唯一开发顺序：先完成 RANK/LIB 主链，再做热点自媒体、六项目真实融合、发布回流和出海。任何 AI 子任务只能提交证据，最终状态由主 Agent 验收后更新。
