# AI Agent 架构

## 10 个 Agent 定义

| Agent | 职责 | 核心能力 |
|---|---|---|
| **Producer** | 工作流规划者 | 将用户目标翻译为 WorkflowPlan（选哪条预设/如何填参/human 节点插入点），产物是数据非控制流 |
| **Story Architect** | 故事架构师 | 世界观构建/人物设定/总纲/分卷大纲/章节细纲 |
| **Character** | 人物设计师 | 人物创建/关系网络/人物弧线/对白风格 |
| **Writer** | 写作者 | 正文生成/续写/按细纲写作 |
| **Editor** | 编辑者 | 去AI味/润色/扩写/缩写/改写 |
| **Reviewer** | 审核者 | 7 维质量评分/OOC/设定冲突/前文一致性/节奏/伏笔校验 |
| **Short Story** | 短篇专家 | 短篇/微小说/情感/悬疑/爆款结构 |
| **Social Media** | 自媒体专家 | 多平台内容适配/爆款标题/SEO/标签/CTA |
| **Trend** | 热点分析师 | 热点抓取/价值评估/选题推荐/爆款分析/扫榜 |
| **Publisher** | 发布者 | 格式适配/平台发布/数据回流 |

## Agent 契约（AgentNode）

每个 Agent 统一实现为：
```python
AgentSpec = {
    role_prompt: str,           # 角色系统 Prompt
    task_prompt_name: str,      # 任务 Prompt 名称
    tool_whitelist: list[str],  # 工具白名单
    input_schema: PydanticModel,
    output_schema: PydanticModel,
    max_retries: int,
    budget_scope: str
}
```

## 关键设计决策

### Agent ≠ 自治对话
Agent 不做自治对话式多 Agent。"多 Agent 协作" = 工作流 DAG 显式编排。Agent 是工作流节点，由引擎按 DAG 边推进，不是互相调用。

### 禁自治的机器约束
- 工具白名单默认不含"调用其它 Agent"这一工具
- CI 静态检查：`agents/**` 不得 import 其它 `agents/**`
- Agent 间触发必须由引擎按 DAG 边推进

### Producer 的边界
Producer 只输出 `WorkflowPlan`（选哪条预设/如何填参/human 节点插入点），产物是**数据**不是控制流。Plan 交给引擎执行，Producer 不参与运行期。

### Agent 注册表
```python
agent_registry = {
    "StoryArchitect": StoryArchitectSpec,
    "Writer": WriterSpec,
    ...
}
# 引擎只能通过 registry 实例化 Agent
```

### 可测试红线
每个 AgentNode 必须有 ≥1 条 golden case（固定 input → 断言 output schema + 关键字段），进 CI。
