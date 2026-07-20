# NovelCraft Personal Studio MVP 开发方案（M1，第 1~5 周）

> MVP 的第一使命是交付“扫榜→分析→全自动原创成书→自动入书库”，第二使命是“热点→自媒体多平台草稿”；灵感→第一章仅作为次要兼容入口。底层以最终形态落地 C1/C2/C3/C4/C5/C8，并遵循《19-开源项目融合基线》。

## 1. 用户旅程

```
注册/登录 → 榜单中心选择平台/榜单/范围 → 采集快照 → 市场分析 → 原创选题
 → 自动在书库创建小说(planning) → 世界观→人物→总纲→卷纲→细纲→第一章→7维审核/返工
 → 继续批量生成/自动连载（生成中始终可在书库查看进度）

次要入口：输入灵感 → 原创立项 → 复用同一成书工作流 → 自动进入书库。
自媒体入口：热点扫描 → 价值/平台适配 → 选题池 → 至少三平台草稿。
```

## 2. 范围

**做**：扫榜成书、统一书库、热点自媒体、灵感兼容入口 + 设计系统v1 + 骨架表 + V1迁移 + SSE + 预算 + 备份告警。
**不做**（M2+ 再做）：30万字完整压测、更多榜单源、真实发布、离线、协作；但不得把扫榜、书库和热点自媒体推迟到M3。

## 3. rank-to-book = 第一条预设工作流；bootstrap 为次要入口

引擎必须支持可恢复的 chain + branch + human；扫榜自动模式可跳过普通确认，但数据源、预算、质量异常必须进入等待态：

```
run(rank_to_book)
 n1 tool:RankScanner       capture_snapshot → ranking_snapshots/items
 n2 agent:Trend            analyze_market   → market_analysis
 n3 agent:Producer         original_topics  → topic_candidates
 n4 branch/human           auto_select_or_confirm
 n5 tool:Library           create_book      → contents(type=novel, source_type=ranking)
 n6 agent:Architect        bible_outline    → worldview/character/outline/detail
 n7 agent:Writer           generate         → chapters
 n8 agent:Reviewer         review_rewrite   → quality gate + reconcile
```
每节点：幂等（node 级 succeeded 即跳过）、失败自动重试 2 次、可单点重跑；全部调用经 Gateway 落 ai_calls；进度经 Redis→SSE。

## 4. 数据模型（M1 一次建齐骨架）

新建：`contents`、`derivations`、`versions`、`workflows`、`workflow_runs`、`run_nodes`、`ai_calls`、`budgets`、`prompts`、`model_routes`、`knowledge_items`（+vectors）、`project_members`、`audit_logs`。
迁移：V1 `novels/chapters/characters` → contents 树 + knowledge_items；迁移脚本双向校验（行数/抽样内容一致），执行前自动备份。

## 5. API（增量）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /api/projects/{id}/novels | 创建小说（content type=novel） |
| POST | /api/novels/{id}/bootstrap | 启动 bootstrap run |
| GET | /api/runs/{id} · /events | 状态 + SSE 进度 |
| POST | /api/runs/{id}/nodes/{key}/confirm | human 节点确认（选标题/放行） |
| POST | /api/runs/{id}/nodes/{key}/retry | 单节点重跑 |
| PUT | /api/contents/{id} | 保存（VersionedRepository 自动快照） |
| POST | /api/contents/{id}/ai/{op} | 选中润色/改写/续写（op 三件套） |
| GET/POST | /api/contents/{id}/versions[/restore] | 版本列表/恢复 |
| GET | /api/ai-calls?run_id= | 追踪查询（成本/输入输出） |

## 6. 前端（5 页 + 设计系统）

0. **设计系统 v1**（第 1~2 周并行）：tokens、暗色原生、Radix/shadcn 定制组件（Button/Input/Dialog/Toast/Progress/RadarChart/DiffView）、布局骨架（侧边项目树 + 主区）；
1. 创建向导（灵感表单，单页）；
2. 生成进度页（8 节点时间线 + 实时日志 + human 确认卡片 + 单点重试）；
3. 审阅页（标题三选一、人物卡、总纲树、7 维雷达 + 问题清单、退回重跑）；
4. 编辑器页（Tiptap + 选中浮条三件套 + 自动保存 + 版本侧栏恢复）；
5. 成本页（本次 run 的 ai_calls 明细，极简表格）。

## 7. 验收标准（M1 门禁）

1. 新用户完成扫榜→分析→原创立项→自动入书库→过审第一章，全程无需看日志；
2. 灵感入口与扫榜入口生成的小说都能在统一书库管理；
3. 热点入口可生成至少三平台稿件；
4. 杀 worker/断网后 run 断点续跑；human 节点挂起24h后仍可继续；
5. 单次成书受预算约束，超限熔断为 PENDING_BUDGET 非失败；
6. 任意保存/AI重写可版本恢复；ai_calls记录9要素；
7. V1迁移可回滚；总测试≥135、三轮自审、备份恢复和告警实收通过；
8. 6个指定开源项目的融合/借鉴记录和许可证门禁通过。

## 8. 周计划

- 周 1：V1 收口（TASK-001/002）+ 骨架迁移设计评审；
- 周 2：骨架表迁移 + V1 数据迁移 + Gateway v1 + 设计系统（并行）；
- 周 3：工作流引擎 v0 + bootstrap 八节点 + SSE；
- 周 4：前端五页；
- 周 5：联调、压测、验收、tag `v2.0.0-m1`、部署。
