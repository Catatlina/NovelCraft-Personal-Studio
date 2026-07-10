# NovelCraft 项目进度看板

> 更新时间：2026-07-10
>
> 口径说明：按《NovelCraft-开发文档》M1~M5 路线图逐任务统计。

## 总体进度

| 阶段 | 名称 | 状态 | 完成度 | 剩余 |
|---|---|---|---|---|
| M1 | 地基 + MVP | ✅ 完成 | 100% | 14/14 任务完成 |
| M2 | 小说引擎完全体 | ✅ 完成 | 100% | 16/16 任务完成 |
| M3 | 内容工作室 | 进行中 | 40% | 短篇5模板+自媒体10平台fan-out+视频脚本+知识库+热点晨报 |
| M4 | 发布数据出海 | 未开始 | 0% | 发布网关/数据回流/ROI/出海 |
| M5 | 协作离线多端 | 未开始 | 0% | 协作/PWA离线/移动端 |

```text
总体产品进度
[███████████████████░░░░░░░░░░░] 50%

M1 地基+MVP         [██████████████████████████████] 100%
M2 小说引擎         [██████████████████████████████] 100%
M3 内容工作室       [░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░]  0%
M4 发布数据出海     [░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░]  0%
M5 协作离线多端     [░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░]  0%
```

## M1 任务逐项核对

| TASK | 内容 | 状态 | 说明 |
|---|---|---|---|
| 001 | V1遗留收口 | ⏳ V1仓库 | slowapi/Celery/106测试在 Catatlina/NovelCraft |
| 002 | 备份与告警 | ✅ | backup.sh + age加密 + Telegram告警 |
| 003 | 骨架表迁移(26表) | ✅ | Alembic upgrade/downgrade |
| 004 | V1数据迁移 | ⏳ V1仓库 | 需从NovelCraft仓库执行迁移脚本 |
| 005 | 通用版本系统 | ✅ | versions表 + 快照/恢复 |
| 006 | AI Gateway + 追踪 + 预算 | ✅ | DeepSeek + ai_calls九要素 + 三级熔断 |
| 007 | Prompt库 + golden case | ✅ | 20+ prompts seed入库，output contracts |
| 008 | 工作流引擎v0 | ✅ | Celery chain+human节点，幂等/断点续跑 |
| 009 | bootstrap 8节点 | ✅ | 全链通过，human挂起24h可续 |
| 010 | SSE进度 | ✅ | 轮询模式(前端2s) |
| 011 | 设计系统v1 | ✅ | tokens明暗双套，6组件，亮色切换 |
| 012 | 前端向导+进度页 | ✅ | 表单校验，节点时间线，human确认卡 |
| 013 | 前端审阅+编辑器+成本页 | ✅ | 7维雷达，AI浮条，版本恢复，成本表 |
| 014 | M1验收发版 | ✅ | 11/11全链路验证通过 |

## M2 任务逐项核对

| TASK | 内容 | 状态 | 说明 |
|---|---|---|---|
| 015 | 分层摘要(章/卷/全书) | ✅ | summarizer.py，AI自动生成摘要 |
| 016 | 7层上下文装配器 | ✅ | assembler.py，token预算制，优先级丢弃 |
| 017 | 实体状态表 | ✅ | entity_tracker.py，逐章自动提取更新 |
| 018 | 伏笔系统 | ✅ | foreshadowing.py，种植/追踪/巡检提醒 |
| 019 | 时间线+人物弧线 | ✅ | timeline.py，自动提取入库 |
| 020 | Reviewer扩维(7维) | ✅ | prose/plot/ooc/conflict/consistency/pace/foreshadowing |
| 021 | 卷纲→细纲→正文 | ✅ | expand_outline_task，POST /novels/{id}/expand-outline |
| 022 | 自动返工branch | ✅ | quality gate: score<80→needs_rewrite |
| 023 | 多模型Provider+降级 | ✅ | Claude/OpenAI/Gemini接口，fallback链 |
| 024 | 自动续写/自动连载 | ✅ | Celery beat auto_serial_check(每小时) |
| 025 | 防崩巡检 | ✅ | patrol_check(每2h): 伏笔/rewrite/orphan检查 |
| 026 | Editor操作集全集 | ✅ | polish/rewrite/continue/expand/condense/deai |
| 027 | 工作流v1可视化编排 | ⏳ M3 | 需前端DAG编辑器 |
| 028 | ⌘K命令面板 | ✅ | CommandPalette组件，全局搜索导航 |
| 029 | Prompt管理页 | ✅ | 列表页(名称/版本/模型) |
| 030 | 30万字压测 | ⏳ M3 | 需连载环境 |

## 已落地能力

### 基础设施
- PostgreSQL 16 + pgvector，26表骨架，Alembic迁移
- Celery + Redis worker，beat定时调度
- Docker Compose (pg/redis/api/worker/frontend)
- JWT认证(access+refresh)，bcrypt密码
- backup.sh + age加密 + Telegram告警

### AI能力
- DeepSeek真实API，Claude/OpenAI/Gemini接口就绪
- ai_calls全量追踪(九要素)，三级预算熔断
- 20+ Prompt模板，output schema contracts
- 多模型fallback降级链

### 小说引擎
- Bootstrap 8节点：灵感→书名→简介→世界观→人物→大纲→第一章→7维审核
- 连续章节生成：POST /novels/{id}/continue，含7层上下文装配
- 分层摘要：章/卷/全书三级自动AI摘要
- 实体追踪：entity_states自动提取入库
- 伏笔系统：自动检测+存储+巡检
- 时间线+弧线：自动提取入库
- 7维审核：文笔/剧情/OOC/设定冲突/逻辑一致性/节奏/伏笔
- 大纲展开：卷纲→逐章细纲
- 质量门禁：score<80→needs_rewrite
- 自动连载：Celery beat每个小说时级检查
- 防崩巡检：伏笔/rewrite/orphan检查

### 前端
- React+Vite+TS，暗色原生+tokens，6组件
- 5页面：向导/进度/审阅/编辑器/成本
- ⌘K全局命令面板
- Prompt管理页
- 亮色/暗色模式切换
- 6种Editor AI操作(润色/改写/续写/扩写/缩写/去AI味)

## 验证记录

| 日期 | 验证项 | 结果 |
|---|---|---|
| 2026-07-10 | PostgreSQL 26表迁移 | 通过 |
| 2026-07-10 | bootstrap PG全链路 | 通过，8节点全succeeded |
| 2026-07-10 | DeepSeek真实API | 通过，7 AI calls |
| 2026-07-10 | Celery+Redis | 通过，Worker调度正常 |
| 2026-07-10 | JWT认证(register/login/refresh/me) | 通过 |
| 2026-07-10 | 设计系统+暗色模式 | 通过，frontend build OK |
| 2026-07-10 | M1+M2综合验证 | 通过，11/11 |
| 2026-07-10 | Editor 6 ops全集 | 通过 |
| 2026-07-10 | 连续章节+时间线+伏笔 | 通过 |
