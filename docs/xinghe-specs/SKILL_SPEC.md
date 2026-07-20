# 星禾AI工作台 · Skill规范

> 版本：V1.0 | 日期：2026-07-20 | 角色：AI Agent架构师

---

## 一、Skill定义

Skill是**可安装、可升级、可卸载**的独立AI能力单元。

### Skill = Input + Prompt + Tools + Output + Evaluation

```
Skill {
    id:          唯一标识
    name:        名称
    version:     版本号（语义化版本）
    category:    分类
    input:       输入参数Schema
    prompt:      Prompt模板（版本化引用）
    tools:       需要的工具列表
    output:      输出格式Schema
    evaluation:  质量评估标准
}
```

---

## 二、Skill模型

```json
{
  "id": "skill_novel_explosive_title",
  "slug": "novel_explosive_title",
  "name": "爆款标题生成",
  "version": "1.2.0",
  "category": "novel",
  "description": "基于市场趋势分析，生成高点击率的小说标题",
  "author": "星禾官方",
  "icon": "sparkles",
  "tags": ["标题", "爆款", "市场分析"],
  "input_schema": {
    "type": "object",
    "properties": {
      "genre": {"type": "string", "description": "小说类型"},
      "theme": {"type": "string", "description": "核心主题"},
      "keywords": {"type": "array", "items": {"type": "string"}},
      "target_audience": {"type": "string"},
      "count": {"type": "integer", "default": 5, "minimum": 1, "maximum": 10}
    },
    "required": ["genre"]
  },
  "output_schema": {
    "type": "array",
    "items": {
      "type": "object",
      "properties": {
        "title": {"type": "string"},
        "score": {"type": "number", "minimum": 0, "maximum": 10},
        "reason": {"type": "string"}
      }
    }
  },
  "prompt_template": "prompt/novel_title_v2",
  "model_preference": {
    "primary": "deepseek-chat",
    "fallback": "claude-sonnet-4-20250514"
  },
  "tools": ["market_data_lookup"],
  "evaluation": {
    "criteria": ["点击率预测", "平台适配", "差异化"],
    "min_score": 6.0
  },
  "estimated_tokens": 800,
  "timeout_seconds": 60
}
```

---

## 三、Skill分类

| 类别 | 示例Skills | 用途 |
|------|-----------|------|
| **novel** | 爆款标题、黄金三章、人物设计、世界观、AI降味、大纲生成 | 小说创作 |
| **content** | 热点选题、SEO标题、多平台改写、摘要生成 | 内容运营 |
| **knowledge** | 知识提取、自动标签、相似度检测、风格学习 | 知识管理 |
| **tool** | 文本润色、语法检查、格式转换、批量处理 | 效率工具 |
| **analysis** | 市场趋势、竞品分析、读者画像、数据解读 | 数据分析 |

---

## 四、Skill生命周期

```
┌──────────┐    ┌──────────┐    ┌──────────┐
│ INSTALL  │ →  │  ENABLE  │ →  │ UPGRADE  │
│  安装     │    │  启用     │    │  升级     │
└──────────┘    └────┬─────┘    └──────────┘
                     │
              ┌──────┴─────┐
              │  DISABLE   │ ← 暂停使用
              │  禁用       │
              └──────┬─────┘
                     │
              ┌──────┴─────┐
              │ UNINSTALL  │ ← 卸载
              └────────────┘
```

### 状态说明

| 状态 | 说明 |
|------|------|
| `installed` | 已安装，默认启用 |
| `active` | 启用，可被调用 |
| `disabled` | 禁用，不可被调用但保留数据 |
| `upgrading` | 升级中 |
| `uninstalled` | 已卸载 |

---

## 五、Skill调用流程

```
用户/Agent触发 → Skill Manager校验
              → 验证输入参数（Schema校验）
              → AI Engine加载Prompt模板
              → 装配上下文（项目/小说/知识库）
              → Provider执行
              → 输出格式校验
              → 质量评估
              → 返回结构化结果
              → 记录使用统计
```

---

## 六、内置Skill清单（V1）

| Slug | 名称 | 分类 | 说明 |
|------|------|------|------|
| `novel_title` | 爆款标题生成 | novel | 基于市场趋势生成高点击率标题 |
| `novel_golden_three` | 黄金三章 | novel | 生成开篇三章吸引读者 |
| `novel_character` | 人物设计 | novel | 创建立体人物角色 |
| `novel_world` | 世界观构建 | novel | 构建完整世界观设定 |
| `novel_outline` | 大纲生成 | novel | 生成完整大纲体系 |
| `novel_deai` | AI降味 | novel | 检测并去除AI写作痕迹 |
| `novel_continue` | 智能续写 | novel | 上下文感知的章节续写 |
| `novel_review` | 质量审核 | novel | 七维质量评分 |
| `content_hotspot` | 热点选题 | content | 基于热点生成选题 |
| `content_rewrite` | 多平台改写 | content | 适配不同平台风格 |
| `knowledge_extract` | 知识提取 | knowledge | 从文本提取结构化知识 |
| `tool_polish` | 文本润色 | tool | 通用文本润色 |
