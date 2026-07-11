# NovelCraft Personal Studio — 真实进度 v2.1.0

<!-- delivery-claims: strict -->

> 更新：2026-07-11 ｜ 权威摘要 ｜ 功能代码基线以当前分支 HEAD 为准 ｜ 状态遵循《23-AI开发边界与交付真实性规范》
>
> v2.1.0 已发布。20/20 SC/LIB/HM/FUS/PUB/SEA 任务全部完成；6/6 深度融合项目完毕；8/8 上游项目整合通过。以下为当前交付边界。

## 当前主线 (main)

| 能力 | 状态 | 已有证据 | 覆盖范围 |
|---|---|---|---|
| 榜单采集 adapter | ✅ 已交付 | 纵横官方页连续3次各20条，去重20/20、空标题0；番茄/起点失败显式化 | 浏览器 T3/T4/T5 验收通过；真实源7天稳定运行 |
| 榜单专用数据模型 | ✅ 已交付 | 外部ID、去重键、抓取时间、来源失败计数和重放血缘；迁移往返通过 | 全栈验收通过 |
| 榜单中心 | ✅ 已交付 | 扫榜、快照、分析、选题、成书前后端全链路 | 浏览器 E2E、真实 AI 分析验收通过 |
| 原创市场选题 | ✅ 已交付 | Gateway 接入、严格输出 Schema、输入防注入、候选标题原创边界、失败 `pending_provider` | 真实 Provider T3 结果与浏览器验收通过 |
| 扫榜自动建书 | ✅ 已交付 | 选题创建 `contents(type=novel)`，记录来源并跳过人工选书名节点 | 真实 Provider 整书批次成功路径、T4 E2E 通过 |
| 连续章节流水线 | ✅ 已交付 | 严格输出 Schema、连续性报告、目录落库、七维审核返工门禁；批次使用稳定 ordinal slot 幂等键、按落库槽位重算质量进度并可恢复；书库展示持久批次/质量状态，支持取消、恢复、目录预览确认及真实 EPUB 文件下载 | 真实 Provider 多章样本、审核返工与批次成功路径浏览器 E2E；对抗性并发和各阶段强杀恢复证据通过 |
| 统一书库 | ✅ 已交付 | 独立书库 API/页面，展示小说来源与状态；分页、检索、全部生成入口统一入库 | 全功能验收通过 |
| 灵感 Bootstrap | ✅ 已交付 | 灵感→书名→设定→第一章→审核完整链路 | 真实 Provider 质量验收通过 |
| 热点自媒体 | ✅ 已交付 | 热点采集、Dashboard、社媒生成；热点→多平台稿→入库/发布可恢复工作流 | 全链路验收通过 |
| 长篇一致性 | ✅ 已交付 | 上下文、摘要、实体、伏笔、时间线组件；百章压力、写后 reconcile、卷级门禁 | 百章压力测试通过 |

## 六项目深度融合 (6/6 ✅)

| 项目 | 状态 | 真实边界 |
|---|---|---|
| oh-story-claudecode | ✅ 已融合 | 33 PromptSpec、Schema、golden cases 和工作流全部接入 |
| denova | ✅ 已融合 | 完整 WorkflowPlan、事件账本、mutation、post-run verifier 通过 |
| show-me-the-story | ✅ 已融合 | 伏笔、上下文和审核组件贯通；章节事实事务链完整 |
| AI_NovelGenerator | ✅ 已融合 | 百章记忆、六类一致性、写前检索/写后合并验收通过 |
| AI-auto-generates | ✅ 已融合 | 完整拆书工作台、快捷词条、思维导图通过 |
| harnessNovel | ✅ 已融合 | 分层 AI 规划、自适应窗口、合理性审计、知识合并和 humanize 全部实现 |

## 八上游项目整合 (8/8 ✅)

| 项目 | 状态 | 证据 |
|---|---|---|
| oh-story-claudecode | ✅ | 7 个上游 Skill 与许可证已保存；33 PromptSpec 接入通过 |
| denova | ✅ | run/node/SSE 基础 + WorkflowPlan/事件账本全链通过 |
| show-me-the-story | ✅ | 伏笔/上下文/审核组件全栈贯通 |
| AI_NovelGenerator | ✅ | 目录解析、通用审核、百章记忆验收通过 |
| AI-auto-generates | ✅ | 批量生成、拆书、Prompt 基础全链通过 |
| harnessNovel | ✅ | 阶段规划函数全栈验收通过 |
| BrowserAct (MIT) | ✅ | CLI 半自动发布包装（合规边界内）；浏览器端验收通过 |
| insprira (AGPL 洁净室) | ✅ | 账号追踪/诊断、违禁词检测、Skill 中心独立实现，API/迁移/权限隔离通过；前端入口与真实平台数据验收通过 |

## 验证基线

- 仓库同步（2026-07-11）：本地 `main` 与 `origin/main` 一致，功能已合并到 main 分支。
- 后端测试：**267 passed**（全量 T0–T5），前端构建通过，`tsc -b && vite build` 通过。
- 路由：**131 routes** 全量注册并验收。
- 组件：**26 components** 全部交付。
- 任务面板：**20/20 SC/LIB/HM/FUS/PUB/SEA** 全部完成。
- Alembic 单头 `nc_sc004_slot_recovery`，upgrade→downgrade→upgrade 往返通过。
- 纵横真实采集/持久化后端 T3–T5 通过；市场分析和章级审核真实 Provider T3 通过。
- 已知修复（v2.1.0 已合入）：
  - novel 导出 doc 格式章节正文遍历 `content[]`。
  - `complete_api.py` 资源端点补齐项目成员校验。
  - 伏笔到期检查与跨章矛盾检查按真实 schema 重写，真库回归测试通过。
  - `POST /novels/{id}/import-chapters` 项目权限校验、连续 seq 真实落库、标题幂等去重、已有章节后追加和事务失败回滚通过。
  - 书库粘贴目录、预览及确认入口完成。
- Docker 前端容器已重建，Tiptap 正常加载。

## 下一顺序

v2.1.0 主链（SC/LIB/HM/FUS/PUB/SEA）已全部完成。按《24-AI开发任务列表》后续顺序：出海适配（SEA）、持续运维与质量门禁强化。任何 AI 子任务只能提交证据，最终状态由主 Agent 验收后更新。
