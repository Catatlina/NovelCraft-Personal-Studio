# Prompt 工程库

## 概述

系统化的 Prompt 管理——版本控制、模型分支、Golden Case 回归、A/B 实验。

## Prompt 数据模型

```sql
prompts(
  id, name, version, model,           -- 三键：name+version+model
  template,                            -- Jinja2 模板
  output_schema,                       -- Pydantic schema 定义
  variables JSONB,                     -- 模板变量说明
  changelog,                           -- 变更日志
  golden_cases JSONB,                  -- [{"input": {...}, "expected": {...}}, ...]
  is_active, created_at
)
```

## 关键特性

### 模型分支
同一 Prompt 的 name+version 下有多个 model 分支：
```
gen_chapter v3:
  ├─ deepseek-chat:   "你是专业网文写手...输出格式..."
  ├─ claude-sonnet-4: "You are a professional web novelist...Output format..."
  └─ gpt-4o:          "As a web novel writer..."
```

不同模型对同一 prompt 的输出结构可能不同，model 分支确保等价性。

### Golden Case 回归
每个 Prompt ≥ 3 条 golden case，进 CI：
```yaml
golden_cases:
  - input: {genre: "玄幻", chapter_num: 1, outline: "..."}
    expected:
      schema_valid: true
      word_count: [2000, 4000]
      has_dialogue: true
```

每次 Prompt 变更自动跑 golden case 回归。

### Prompt 实验室
同 input × {prompt 版本 / 模型} 矩阵批跑：
```
输入：同一章大纲
  ├─ gen_chapter v2 × deepseek-chat
  ├─ gen_chapter v2 × claude-sonnet-4
  ├─ gen_chapter v3 × deepseek-chat
  └─ gen_chapter v3 × claude-sonnet-4

→ 质量分 + 成本 + 延迟对比视图
```

### 渲染引擎
- Jinja2 模板
- 支持条件/循环/过滤器
- 变量来自上下文装配 + 用户输入
- 渲染结果 + 变量快照落 ai_calls.input

## Prompt 生命周期

草稿 → 测试（golden case 全绿）→ 激活 → 废弃

废弃的 Prompt 不删除（ai_calls 有历史引用），标记 is_active=false。
