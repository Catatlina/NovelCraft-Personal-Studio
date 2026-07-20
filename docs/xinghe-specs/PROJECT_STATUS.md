# 星禾AI工作台 · 项目状态

> 版本：V1.0 | 日期：2026-07-20 | 自动生成于每次迭代后更新
>
> ⚠️ 本文档必须保持最新。防止AI重复开发已完成功能。

---

## 当前版本

**V3.0.0**（NovelCraft V2.2 → 星禾AI工作台 V3.0.0）

---

## 已完成功能 ✅

### 平台底座

| 功能 | 状态 | 备注 |
|------|------|------|
| 用户注册/登录 | ✅ | JWT + BYOK |
| 项目CRUD | ✅ |  |
| 统一鉴权(authz.py) | ✅ |  |
| 全局错误信封 | ✅ | {code,message,data} |
| 计费系统(billing) | ✅ | 套餐/预算/用量 |
| 操作日志 | ✅ |  |

### AI能力

| 功能 | 状态 | 备注 |
|------|------|------|
| AI Provider集成 | ✅ | DeepSeek/Claude/OpenAI/Gemini |
| AI调用网关(gateway.py) | ✅ | 断路器/重试/预算 |
| Prompt注册表 | ✅ | prompt_registry.py |
| Token统计 | ✅ | ai_calls表 |
| 成本追踪 | ✅ | 实时预算同步 |

### 小说App

| 功能 | 状态 | 备注 |
|------|------|------|
| 扫榜中心 | ✅ | 番茄/起点/纵横 |
| 10层排行分析 | ✅ |  |
| 书库管理 | ✅ | 软删除级联 |
| 自动成书(Bootstrap) | ✅ | 四阶段20节点 |
| 编辑器(Tiptap) | ✅ | novel-prose排版 |
| 去AI化(De-AI) | ✅ | 7层流水线 |
| 伏笔系统 | ✅ |  |
| 时间线 | ✅ |  |
| 审核雷达图 | ✅ | 七维评分 |

### 内容运营

| 功能 | 状态 | 备注 |
|------|------|------|
| 热点采集 | ✅ | 多平台聚合 |
| 每日晨报 | ✅ | 真实采集 |
| 知识库 | ✅ | RAG+向量检索 |
| 风格学习 | ✅ |  |
| 发布网关 | ✅ | 15平台 |

### 协作

| 功能 | 状态 | 备注 |
|------|------|------|
| 邀请/成员管理 | ✅ |  |
| 操作日志 | ✅ |  |

### 前端

| 功能 | 状态 | 备注 |
|------|------|------|
| 19个Tab页面 | ✅ |  |
| Design Token(doc12) | ✅ | CSS变量双模式 |
| 命令面板(⌘K) | ✅ |  |
| 暗/亮模式 | ✅ |  |
| PWA基础 | ✅ | manifest + sw.js |

### 基础设施

| 功能 | 状态 | 备注 |
|------|------|------|
| Docker Compose部署 | ✅ |  |
| Nginx反向代理 | ✅ | SSE优化 |
| Alembic迁移(17个) | ✅ | 单头线性 |
| 后端测试(493+) | ✅ | pytest |
| 前端测试(9/9) | ✅ | vitest |
| E2E测试 | ✅ | Playwright |
| SAST CI | ✅ |  |
| 每日备份 | ✅ | pg_dump sidecar |

---

## 进行中 🔄

| 功能 | 进度 | 负责人 |
|------|------|--------|
| /docs文档体系建立 | ✅ 完成 | AI Agent |
| GitHub自动同步 | ✅ 完成 | AI Agent |
| CSS Token化 | ✅ 完成 | AI Agent |
| AI Engine统一入口 + SSE Chat | ✅ 完成 | AI Agent |
| 项目审计报告 | ✅ 完成 | AI Agent |
| 工作台首页（WorkspaceDashboard） | ✅ 完成 | AI Agent |
| Skill系统（5内置 + API + 前端） | ✅ 完成 | AI Agent |
| Agent系统（3内置 + API + 前端） | ✅ 完成 | AI Agent |
| AI对话页面（AIChat SSE流式） | ✅ 完成 | AI Agent |
| 小说App模块化（apps/novel） | ✅ 完成 | AI Agent |
| 内容/热点App脚手架 | ✅ 完成 | AI Agent |
| 移动端 | 🔲 Phase 3 | — |
| Plugin市场 | 🔲 Phase 4 | — |
| 内容创作App | P2 | Phase 2 |
| 移动Web适配 | P2 | Phase 2 |
| Android App | P3 | Phase 3 |
| Plugin Marketplace | P3 | Phase 4 |

---

## 已知Bug 🐛

| ID | 描述 | 严重程度 | 状态 |
|----|------|----------|------|
| — | 暂无记录 | — | — |

---

## 下一步计划

1. `/docs` 文档体系建立完成
2. 项目审计（PROJECT_AUDIT.md）
3. 设计系统对齐
4. AI Engine封装
5. 工作台首页
6. Skill系统基础
