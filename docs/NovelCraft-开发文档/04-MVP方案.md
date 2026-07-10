# NovelCraft Personal Studio MVP 开发方案（M1，第 1~5 周）

> MVP 的双重使命：① 交付用户闭环（灵感→第一章）；② **以最终形态落地五个平台能力骨架（C1 内容/C2 工作流/C3 网关/C5 版本/C8 追踪）**——宁可慢一周，不留返工债。V1 已有 80% 零件（认证、CRUD、DeepSeek 客户端、Prompt 引擎、状态机、7 维审核、限流），MVP 是"换骨架 + 串流水线"。

## 1. 用户旅程

```
注册/登录 → 创建项目与小说 → 输入灵感（一句话~一段 + 题材/风格/目标字数）
 → bootstrap 工作流：书名(3候选)→简介卖点→世界观→人物(3~6)→总纲→第一章→7维审核
 → 审阅页（human 节点：选标题/确认或退回重跑单步）
 → 编辑器修改（选中润色/改写/续写）或一键按审核意见重写
 → 保存（自动版本快照）
```

## 2. 范围

**做**：上述闭环 + 设计系统 v1 + 骨架表全建 + V1 数据迁移 + SSE 进度 + 三级预算 + 备份告警。
**不做**（M2+ 再做）：第二章/连载、伏笔/时间线、多模型、可视化工作流编排、自媒体/热点/发布、离线、协作页（表结构先建）。

## 3. bootstrap = 第一条预设工作流（工作流引擎 v0）

引擎 v0 只支持线性 chain + human 节点，但表结构用最终版（workflows/workflow_runs/run_nodes）：

```
run(bootstrap, novel_id)
 n1 agent:StoryArchitect  gen_titles      → contents(novel).meta.title_candidates
 n2 human                 选定标题（前端确认，run 挂起）
 n3 agent:StoryArchitect  gen_synopsis    → meta.synopsis / selling_points
 n4 agent:StoryArchitect  gen_worldview   → knowledge_items(kind=worldview)
 n5 agent:Character       gen_characters  → knowledge_items(kind=character)×N
 n6 agent:StoryArchitect  gen_outline     → meta.outline
 n7 agent:Writer          gen_chapter1    → contents(type=chapter, parent=novel)
 n8 agent:Reviewer        review_7dim     → run_nodes.output + 审阅页展示
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

1. 新用户 ≤15 分钟灵感→过审第一章，全程无需看日志；
2. 杀 worker/断网后 run 断点续跑；human 节点挂起 24h 后确认仍可继续；
3. 单次 bootstrap 成本 ≤¥2 预算，超限熔断为 PENDING_BUDGET 非失败；
4. 任意保存/AI 重写可版本恢复；ai_calls 对每次调用记录 9 要素完整；
5. V1 数据迁移校验通过且可回滚；
6. 单测新增 ≥30（引擎 v0/幂等/预算/版本/迁移），总 ≥135 全绿；lint/type/build 过；三轮自审报告归档；
7. 备份恢复演练 1 次通过；失败告警实际收到 1 条测试通知。

## 8. 周计划

- 周 1：V1 收口（TASK-001/002）+ 骨架迁移设计评审；
- 周 2：骨架表迁移 + V1 数据迁移 + Gateway v1 + 设计系统（并行）；
- 周 3：工作流引擎 v0 + bootstrap 八节点 + SSE；
- 周 4：前端五页；
- 周 5：联调、压测、验收、tag `v2.0.0-m1`、部署。
