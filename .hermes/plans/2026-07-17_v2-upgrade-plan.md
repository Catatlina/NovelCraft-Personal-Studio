# NovelCraft V2.0 全面升级实施方案

> **For Hermes:** Use 3 parallel delegate_task agents to implement the 3 major domains below.
> **文档依据**: 用户需求文档（10问题 + 十四节V2.0规范）
> **当前状态**: PROJECT_PROGRESS.md — 大部分功能 🧪待验收，565 passed/9 skipped

**Goal:** 解决10个用户反馈问题，将NovelCraft升级为商业级AI小说创作平台

**Architecture:** FastAPI + React/TS + DeepSeek + PostgreSQL + Celery + Redis

---

## Phase 1: 扫描器 + 书库 (Agent A — Problems 1, 2, 8)

### 1.1 番茄全榜扫描
- **文件**: `backend/app/services/ranking_adapter.py` `_fanqie_meta()` + `fetch_fanqie_ranking()`
- **当前**: 仅西幻榜 (`category_id=17`)
- **目标**: 支持全部榜单类型（主榜/全站/新书/分类/热销/完结/推荐/月/周/日榜）
- **实现**: 
  1. 从番茄rank页提取所有category_id→名称映射
  2. `fetch_fanqie_ranking()` 新增 `category_id` 和 `page` 参数
  3. 新增 `scan_all_fanqie_leaderboards()` 遍历所有分类+分页
  4. 支持自动翻页、断点续扫、失败重试
  5. 后台可配置采集数量 (50/100/200/500/1000, 默认100)

### 1.2 起点/纵横采集增强
- **文件**: `backend/app/services/ranking_adapter.py` `fetch_qidian_ranking()` / `fetch_zongheng_ranking()`
- **当前**: 每平台仅采集少量
- **目标**: 默认100本以上，支持分页+增量更新+断点恢复
- **实现**: 翻页逻辑 + 去重(按title+author SHA256) + 合并

### 1.3 书库删除功能
- **后端**: `backend/app/api/v1/ranking.py` `library_router` — 新增 `DELETE /books/{id}` + `DELETE /chapters/{id}` + `POST /books/batch-delete`
- **前端**: `frontend/src/components/BookLibrary.tsx` — 每条书籍+章节增加删除按钮、二次确认弹窗、批量删除

---

## Phase 2: 编辑器 + AI质量 (Agent B — Problems 3, 4, 5)

### 2.1 编辑器小说排版
- **文件**: `frontend/src/components/RichEditor.tsx` + `Editor.tsx`
- **目标**: 对标番茄作家助手 — 自动断句、自动分段、首行缩进、段间距、行高、阅读宽度、标题样式、章节编号、引号规范
- **实现**:
  1. `formatNovelText()` 工具函数: 段落分割→每段首行缩进2em→段间距1.5em→行高1.8
  2. CSS类 `.novel-prose` 覆盖字体/行高/间距/缩进
  3. 字符统计: 字数/预计阅读时间/段数
  4. 导出预览模式（只读、仿纸质书排版）

### 2.2 编辑器UI重构
- **文件**: `frontend/src/components/RichEditor.tsx` 重写
- **功能**: 顶部工具栏、左侧目录树(已有chapter select)、右侧AI助手面板、底部状态栏、浮动工具栏(选中文本)、全屏模式、夜间模式、专注模式、历史版本
- **设计**: 暗色科技风(`--nc-*` tokens)

### 2.3 七层去AI味润色管线
- **后端新文件**: `backend/app/services/deai_pipeline.py`
- **七层**: 去AI味→口语化→节奏优化→人物一致性→上下文一致性→重复表达去除→最终润色
- **API**: `POST /api/v1/contents/{id}/deai` 接收content_id，返回7层结果+评分
- **前端**: Editor右侧AI面板增加"去AI味"按钮+进度展示+各层评分
- **评分体系**: AI味指数(0-100)、重复率(%)、人物一致性(0-10)、剧情节奏(0-10)、情绪曲线
- **自动审查**: 生成后自动跑七维评分，不合格自动重新生成

---

## Phase 3: 热点+分析+选题池 (Agent C — Problems 6, 7, 9, 10)

### 3.1 热点多平台聚合
- **后端**: `backend/app/services/hotspot_collector.py` — 已有百度/知乎/微博，扩展: 公众号/今日头条/小红书/抖音/快手/Google Trends/B站
- **API**: `GET /hotspots/overview` — 今日热点总览(总结+分类+趋势+分析+爆文预测+推荐选题)
- **前端**: `HotspotDashboard.tsx` — 多平台tab+统一排序+热度评分+分页

### 3.2 一键生成文章 + 文库
- **后端**: `POST /hotspots/generate` 已有，增强: 支持公众号/头条/小红书/百家号/知乎/短视频脚本/口播稿
- **新API**: `GET /articles` (文库列表) + `GET /articles/{id}` (详情) + `DELETE /articles/{id}` + `PUT /articles/{id}` (编辑)
- **前端**: HotspotDashboard新增"一键生成"按钮 + 文库Tab(标题/简介/平台/时间/状态/查看详情/编辑/删除/再次生成)

### 3.3 十层分析模型
- **后端新文件**: `backend/app/services/ten_layer_analysis.py`
- **十层**: 
  1. BookProfile(榜单元数据)
  2. GenreReport(题材分析)
  3. SellingPoints(卖点分析)
  4. Golden3Chapter(黄金三章)
  5. PlotRhythm(剧情节奏)
  6. Character(人物分析)
  7. WorldBuilding(世界观)
  8. StyleReport(文风分析)
  9. ReaderReport(读者反馈)
  10. AIInsight(AI综合推演)
- **API**: `POST /ranking/analyze` — 支持单平台/多平台/全平台分析
- **输出**: `ScanResult/` 目录结构(JSON + Markdown + PDF)

### 3.4 选题池改造
- **后端**: 新增 `POST /topics/{id}/bookmark` (加入备选) + `DELETE /topics/{id}` + `POST /topics/batch-delete`
- **规则**: 未加入备选的选题下一轮自动清空; 备选池永久保留
- **前端**: RankingCenter.tsx 每条选题增加"备选⭐"+"删除🗑"按钮; 备选池独立Tab

---

## 实施顺序

### 第一步 (并行): 3个Agent同时开发
| Agent | 域 | 预估改动 |
|-------|-----|---------|
| Agent A | Scanner + Book Library | ~8 files, ~400 lines |
| Agent B | Editor + De-AI Pipeline | ~10 files, ~600 lines |
| Agent C | Hotspot + Analysis + Topics | ~10 files, ~700 lines |

### 第二步: 集成验证
- 全量 pytest (目标: 565+ tests green)
- 前端 npm run build 通过
- 浏览器端到端验收

### 第三步: 部署
- 新加坡 VPS 更新代码
- systemd restart
- 生产验证

---

## 文件变更清单

### Agent A (Scanner + Library)
| 操作 | 文件 |
|------|------|
| 修改 | `backend/app/services/ranking_adapter.py` |
| 修改 | `backend/app/api/v1/ranking.py` |
| 新增 | 番茄所有榜单采集逻辑 |
| 修改 | `frontend/src/components/BookLibrary.tsx` |
| 修改 | `frontend/src/components/RankingCenter.tsx` |

### Agent B (Editor + De-AI)
| 操作 | 文件 |
|------|------|
| 重写 | `frontend/src/components/RichEditor.tsx` |
| 修改 | `frontend/src/components/Editor.tsx` |
| 新增 | `backend/app/services/deai_pipeline.py` |
| 新增 | `backend/app/api/v1/deai.py` |
| 修改 | `backend/app/main.py` (注册路由) |
| 新增 | `frontend/src/styles/novel-prose.css` |

### Agent C (Hotspot + Analysis + Topics)
| 操作 | 文件 |
|------|------|
| 修改 | `backend/app/services/hotspot_collector.py` |
| 新增 | `backend/app/services/ten_layer_analysis.py` |
| 修改 | `backend/app/api/v1/hotspots.py` |
| 新增 | `backend/app/api/v1/articles.py` |
| 修改 | `backend/app/api/v1/ranking.py` (分析+选题池) |
| 修改 | `frontend/src/components/HotspotDashboard.tsx` |
| 修改 | `frontend/src/components/RankingCenter.tsx` |
| 修改 | `backend/app/main.py` (注册路由) |

---

## 验证标准
- [ ] 番茄采集 ≥10个榜单类型，每个≥100本
- [ ] 起点/纵横 ≥100本/平台
- [ ] 书库可正常删除(单本+批量)
- [ ] 编辑器段落分明、首行缩进、阅读舒适
- [ ] 编辑器左侧目录+右侧AI面板可用
- [ ] 七层去AI味管线完整可调用
- [ ] 热点≥5平台聚合显示
- [ ] 热点→一键生成文章→文库查看完整闭环
- [ ] 十层分析模型API可调用
- [ ] 选题池备选/删除功能正常
- [ ] 全量pytest 565+ passed
- [ ] npm build 通过
