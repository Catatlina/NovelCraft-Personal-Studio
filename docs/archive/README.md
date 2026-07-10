# Historical Documentation Archive

> **唯一保留**：`NovelCraft-V2-Personal-Pro-Plus-Full-Documentation/`（37 份完整文档）

## 文档清单（00~36）

| 编号 | 文档 | 说明 |
|---|---|---|
| 00 | 项目总览 | 产品定位、10 大原则、技术栈、功能模块 |
| 01 | 完整 PRD 需求文档 | 愿景/使命/用户画像/功能范围/非功能需求 |
| 02 | 功能需求详细说明 | 小说/自媒体/热点/知识库/编辑器逐类展开 |
| 03 | 用户流程设计 | 核心用户旅程/工作流交互/编辑器交互/离线交互 |
| 04 | 系统总体架构 | 架构图/8 大平台能力/服务拓扑 |
| 05 | 技术选型说明 | 全栈选型理由/明确不引入/关键设计决策 |
| 06 | 数据库设计文档 | 26 表概述/建表拓扑/命名规范 |
| 07 | 数据库 ER 关系说明 | 实体关系图/Content 树/版本系统/工作流链 |
| 08 | SQL 建表规划 | 核心表 DDL（contents/versions/workflows/ai_calls/knowledge） |
| 09 | API 接口设计 | 约 80 端点/13 模块/REST + SSE |
| 10 | 后端工程规范 | 目录结构/三条铁律/编码规范/错误处理 |
| 11 | 前端工程规范 | 技术选型/设计系统/组件规范/性能 |
| 12 | UI 设计规范 | 对标基准/色彩/排版/间距/组件库 |
| 13 | 编辑器详细设计 | Tiptap/三栏工作台/AI 浮条/版本侧栏 |
| 14 | AI Agent 架构 | 10 Agent 定义/契约/注册表/禁自治约束 |
| 15 | Agent 工作流程 | Bootstrap/连载/一稿多平台/晨报/执行语义 |
| 16 | Context Hub 记忆系统 | 7 层上下文装配/分层摘要/实体状态表 |
| 17 | 小说智能引擎 | 创作流水线/大纲/正文/防崩/伏笔/7 维审核 |
| 18 | 长篇小说生产系统 | 全生命周期/世界观/人物/大纲/自动连载 |
| 19 | 短篇小说生产系统 | 5 类短篇/爆款模板/生产流程/知识复用 |
| 20 | 自媒体生产系统 | 10 平台适配/一稿多平台 fan-out/批量生产 |
| 21 | 热点监控系统 | 数据源/adapter/AI 分析/选题库/每日晨报 |
| 22 | 内容矩阵系统 | 跨平台矩阵管理/血缘追踪/ROI 分析 |
| 23 | 内容复用系统 | 复用形态/工作流/去重变异/衍生追溯 |
| 24 | 短视频脚本系统 | 抖音/小红书/B站 脚本/分镜/钩子/口播 |
| 25 | 多模型 AI 系统 | 4 Provider/Gateway/路由降级/A·B/预算/成本 |
| 26 | Prompt 工程库 | 模型分支/Golden Case/实验室/生命周期 |
| 27 | 自动生产流水线 | 连载/短篇/fan-out/晨报/执行保障/监控 |
| 28 | 自动发布系统 | 三模式/国内约束/Adapter/安全检查/数据回流 |
| 29 | 出海系统设计 | 翻译管线/本地化/禁忌/海外平台/KDP 适配 |
| 30 | 部署运维文档 | Compose/首次部署/备份/健康检查/告警/升级 |
| 31 | 安全设计 | JWT/RBAC/加密/Web 安全/AI 安全/审计/检查清单 |
| 32 | 测试验收标准 | 分层策略/Golden Case/M1~M2 门禁/性能基线 |
| 33 | 开发路线规划 | M1~M5 里程碑/核心任务/红线 |
| 34 | 开发任务拆解 | 52 任务全量/M1 14 任务详表/依赖关系 |
| 35 | Git 协作规范 | 分支策略/Commit/PR/CI/文档纪律/发布流程 |
| 36 | 商业化规划 | 触发条件/可能方向/架构兼容性 |

## 当前基线

此归档文档为 V2 Personal Pro+ 历史版本。当前开发基线为：

- `docs/NovelCraft-开发文档/`（18 份 V2.1 文档）— 权威、活跃维护的开发文档集
- `docs/IDEA.md`
- `PROJECT_PROGRESS.md`

开发工作以 V2.1 文档为准。

## 已清理

以下冗余文档集已移除（内容与 Full-Documentation 重复）：

- ~~NovelCraft-V2-All-Documentation/~~（含 V2-Documentation + Enterprise-Documentation）
- ~~NovelCraft-V2-Personal-Pro-Plus-Complete-Documentation/~~

仅保留最完整的一套：**NovelCraft-V2-Personal-Pro-Plus-Full-Documentation**（37 文档，零空壳）。

## Not Included

以下本地归档文件有意未提交：

- `/Users/genius/Documents/NovelCraft-V2-All-Documentation.zip`
- `/Users/genius/Documents/NovelCraft-V2-Personal-Pro-Documentation.zip`
- 等

理由：.zip 文件重复了已提交的 Markdown；.tar 二进制快照不适合 Git 追踪（约 137 MB），如有需要应使用 GitHub Releases 或 Git LFS。
