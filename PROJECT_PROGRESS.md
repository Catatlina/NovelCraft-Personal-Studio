# NovelCraft Personal Studio — v2.0.0 进展

> `1d49a3d` · 154 tests (149 core + 5 ranking) · 21 components · 82 backend files · 8 agents

## 本轮交付 (2026-07-11)

### 依赖安装
| 包 | 用途 | 状态 |
|---|---|---|
| pgvector 0.6.0 | PostgreSQL 向量检索 | ✅ Ubuntu |
| pymupdf | PDF 解析 | ✅ |
| python-docx | Word 解析 | ✅ |
| @tiptap/react | 编辑器 | ✅ |
| diff-match-patch | 文本差量 | ✅ |

### 功能交付
| 类别 | 需求 | 状态 |
|---|---|---|
| C6 | 伏笔到期注入 (gen_next_chapter 前检测) | ✅ |
| C6 | 跨章矛盾检测 | ✅ |
| C6 | 弧线偏移校验 | ✅ |
| C4 | pgvector 向量检索 + 语义搜索 | ✅ |
| C4 | 知识库浏览页 (KnowledgeBrowser) | ✅ |
| C3 | Agent 注册表 (8 agent) + API | ✅ |
| C2 | 工作流暂停/恢复/取消 | ✅ |
| UI | Tiptap 编辑器 (替换 RichEditor) | ✅ |
| C1 | 榜单 adapter (番茄/起点/纵横 - 无需 API Key) | ✅ |

### 开源融合
| 项目 | 融合方式 | 状态 |
|---|---|---|
| oh-story (MIT) | 7 skills 直接导入 (125K chars) | ✅ |
| denova (Apache) | 架构概念移植 | ✅ |
| show-me-the-story (MIT) | 行为移植 (Go→Python) | ✅ |
| AI_NovelGenerator (AGPL) | 洁净室等价实现 | ✅ |
| AI-auto-generates (Apache) | 功能概念移植 | ✅ |
| harnessNovel (GPL) | 洁净室等价实现 | ✅ |

## 硬阻碍状态

| 阻碍 | 状态 | 影响需求数 |
|---|---|---|
| pgvector | ✅ **已解** | 5→0 |
| 离线 L2/L3 | ❌ 仍阻 | 3 |
| V1 数据库 | ❌ 仍阻 | 1 |
| 多平台 API Key | ❌ 仍阻 | ~15 |

## 进度条

```
M1 █████████████████████████░ 88%
M2 ███████████████████░░░░░ 70%
M3 ██████████████░░░░░░░░░ 55%
M4 ██████████░░░░░░░░░░░░░ 40%
M5 ██████░░░░░░░░░░░░░░░░░ 25%
─────────────────────────────
总体 ███████████████░░░░░░ 62%
```
