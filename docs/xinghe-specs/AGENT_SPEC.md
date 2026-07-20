# 星禾AI工作台 · Agent规范

> 版本：V1.0 | 日期：2026-07-20 | 角色：AI Agent架构师
>
> ⚠️ Agent不是简单Prompt。必须结构化定义。

---

## 一、Agent定义

### Agent = Goal + Memory + Skills + Tools + Workflow

```
Agent {
    goal:       明确的目标（做什么）
    memory:     记忆系统（记住什么）
    skills:     可调用的Skills（有什么能力）
    tools:      可使用的工具（能操作什么）
    workflow:   执行流程（怎么做）
}
```

### 禁止：把Agent写成超级Prompt

```
❌ 错误：
Agent = "你是一个专业的小说作者，你需要..."（一个长Prompt）

✅ 正确：
Agent = {
    goal: "创作一部高质量的市场导向型小说",
    skills: ["爆款标题", "黄金三章", "人物设计", "AI降味"],
    tools: ["web_search", "ranking_scanner", "content_editor"],
    workflow: {
        steps: [
            { id: "market_analysis", skill: "market_analysis" },
            { id: "topic_selection", skill: "topic_selection", depends_on: ["market_analysis"] },
            ...
        ]
    }
}
```

---

## 二、Agent模型

```json
{
  "id": "agent_novel_author",
  "name": "小说作者Agent",
  "description": "全自动完成从市场分析到成书的全流程",
  "version": "1.0.0",
  "category": "content_creation",

  "goal": {
    "type": "novel_creation",
    "description": "创作一部高质量的市场导向型小说",
    "success_criteria": [
      "完成所有章节生成",
      "质量评分 ≥ 7.0",
      "AI味评分 ≤ 3.0"
    ]
  },

  "model_preference": {
    "primary": "claude-sonnet-4-20250514",
    "fallback": "deepseek-chat",
    "max_tokens_per_step": 8000
  },

  "memory": {
    "type": "conversation_buffer",
    "max_tokens": 8000,
    "persist_across_runs": true,
    "key_fields": ["characters", "world_building", "plot_threads"]
  },

  "skills": [
    "skill_market_analysis",
    "skill_topic_selection",
    "skill_outline_generation",
    "skill_character_design",
    "skill_chapter_generation",
    "skill_quality_check",
    "skill_deai_polish"
  ],

  "tools": [
    "tool_web_search",
    "tool_ranking_scanner",
    "tool_content_editor",
    "tool_knowledge_retrieval"
  ],

  "workflow": {
    "type": "dag",
    "steps": [
      {
        "id": "market_analysis",
        "name": "市场分析",
        "skill": "skill_market_analysis",
        "timeout_seconds": 300,
        "retry": { "max": 2, "backoff": "exponential" }
      },
      {
        "id": "topic_selection",
        "name": "选题",
        "skill": "skill_topic_selection",
        "depends_on": ["market_analysis"],
        "human_approval_required": true
      },
      {
        "id": "outline",
        "name": "大纲",
        "skill": "skill_outline_generation",
        "depends_on": ["topic_selection"]
      },
      {
        "id": "characters",
        "name": "人物设计",
        "skill": "skill_character_design",
        "depends_on": ["outline"]
      },
      {
        "id": "chapters",
        "name": "章节生成",
        "skill": "skill_chapter_generation",
        "depends_on": ["characters"],
        "loop": { "max_iterations": 120, "condition": "chapters_remaining > 0" }
      },
      {
        "id": "quality_check",
        "name": "质量审核",
        "skill": "skill_quality_check",
        "depends_on": ["chapters"],
        "retry_on_fail": true
      }
    ]
  },

  "trigger": {
    "type": "manual",
    "schedule": null
  },

  "status": "active"
}
```

---

## 三、Agent生命周期

```
创建 (Create)
    ↓
配置 (Configure) → 绑定Skills/Tools/Workflow
    ↓
激活 (Activate)
    ↓
运行 (Run)
    ├── idle → pending → running
    ├── waiting_human → running  (需要人工确认)
    └── failed → retry → running
    ↓
完成 (Complete) / 失败 (Failed)
    ↓
停用 (Deactivate)
```

---

## 四、预置Agent（V1）

| Agent | 目标 | 触发方式 |
|-------|------|----------|
| **小说作者Agent** | 扫榜→选题→大纲→人物→章节→审核 | 手动触发 |
| **内容审核Agent** | 自动检查AI味道/一致性/质量 | 章节生成后自动 |
| **热点分析Agent** | 定时扫描热点，生成每日晨报 | 定时（每6小时） |
| **发布助手Agent** | 多平台内容适配+发布排期 | 手动触发 |

---

## 五、Agent开发规范

### 5.1 开发流程

```
1. 定义Goal：明确Agent要完成什么
2. 拆解Workflow：分解为可执行的步骤DAG
3. 选择Skills：每个步骤需要什么Skill
4. 配置Tools：Agent可以使用什么工具
5. 设置Memory：Agent需要记住什么
6. 定义Human Gates：哪些步骤需要人工确认
7. 测试：模拟运行整个Workflow
```

### 5.2 禁止事项

| ❌ 禁止 | ✅ 正确做法 |
|--------|-----------|
| 把Agent写成一个长Prompt | 结构化定义 Goal + Workflow + Skills |
| Agent直接调Provider | 通过Skill → AI Engine调用 |
| Agent跳过人工确认 | 关键节点（选题/发布）必须人工确认 |
| Agent无超时限制 | 每个Step必须设timeout |
| Agent无错误处理 | 必须定义 retry/failback 策略 |

### 5.3 人工确认节点（Human Gate）

以下节点必须人工确认：

- **选题确认**：Agent推荐选题 → 用户选择/修改
- **书名确认**：Agent生成书名 → 用户选择
- **大纲确认**：Agent生成大纲 → 用户审核
- **发布确认**：Agent准备发布 → 用户最终确认

---

## 六、Agent与Skill的关系

```
Agent = 编排层（做什么、怎么做）
Skill = 能力层（具体执行某个AI任务）

Agent调用Skill，Skill调用AI Engine。

示例：
小说作者Agent
├── 市场分析 → skill_market_analysis → AI Engine → Provider
├── 选题     → skill_topic_selection  → AI Engine → Provider
├── 大纲     → skill_outline_generation → AI Engine → Provider
└── 章节     → skill_chapter_generation → AI Engine → Provider
```

---

## 七、Agent运行状态事件

Agent运行时通过SSE推送以下事件：

| 事件 | 说明 |
|------|------|
| `agent.run.started` | Agent开始执行 |
| `agent.run.step.started` | 某个Step开始 |
| `agent.run.step.progress` | Step执行中（流式输出） |
| `agent.run.step.completed` | Step完成 |
| `agent.run.step.failed` | Step失败 |
| `agent.run.waiting_human` | 等待人工确认 |
| `agent.run.completed` | Agent执行完成 |
| `agent.run.failed` | Agent执行失败 |

---

> **下一步**：阅读 [ARCHITECTURE.md](./ARCHITECTURE.md) 了解Agent在系统中的位置
