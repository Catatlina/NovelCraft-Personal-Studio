# Agent 工作流程

## Agent 协作模式

所有 Agent 协作由工作流引擎显式编排。Agent 本身不"对话"，它们是被工作流串联的执行节点。

## Bootstrap 工作流示例

用户创建小说 → Producer 规划 → 引擎执行：

```
run(bootstrap, novel_id)
 n1 agent:StoryArchitect  gen_titles      → 书名候选(3)
 n2 human                 选定标题         → 挂起等用户确认
 n3 agent:StoryArchitect  gen_synopsis    → 简介/卖点
 n4 agent:StoryArchitect  gen_worldview   → 世界观设定
 n5 agent:Character       gen_characters  → 人物(3~6个)
 n6 agent:StoryArchitect  gen_outline     → 总纲
 n7 agent:Writer          gen_chapter1    → 第一章正文
 n8 agent:Reviewer        review_7dim     → 7维审核报告
```

## 长篇连载流水线

```
 n1 agent:StoryArchitect  gen_outline     → 卷纲/细纲（先审，便宜 20 倍）
 n2 human                 审核大纲         → 确认/退回
 n3 agent:Writer          gen_chapter     → 生成正文
 n4 agent:Reviewer        review          → 质量分
 n5 tool:branch           分数<80?        → 返工（最多 2 轮）
 n6 agent:Editor          polish          → 最终润色
 n7 human                 最终确认         → 发布/存档
```

## 一稿多平台 Fan-out

```
 source_content (公众号长文)
  ├─ agent:SocialMedia  gen_toutiao    → 头条版（SEO标题+关键词）
  ├─ agent:SocialMedia  gen_xhs        → 小红书版（短笔记+emoji+标签）
  ├─ agent:SocialMedia  gen_zhihu      → 知乎版（问答格式）
  ├─ agent:SocialMedia  gen_medium     → Medium英文版
  └─ agent:SocialMedia  gen_substack   → Substack版
```

## 每日热点晨报（定时自动化）

```
 beat 触发(每天 09:00)
 n1 tool:fetch_trends   抓热点         → 新闻热榜/行业热点
 n2 agent:Trend          analyze        → 价值评估/平台判断
 n3 agent:Trend          recommend      → 选题推荐
 n4 agent:SocialMedia    gen_wechat     → 公众号草稿
 n5 agent:SocialMedia    gen_toutiao    → 头条草稿
 n6 agent:SocialMedia    gen_xhs        → 小红书草稿
 n7 human                最终审核        → 确认发布/修改
```

## 执行语义

- **节点级幂等**：succeeded 即跳过，重跑不产生脏数据
- **Run 级断点续跑**：杀 worker 后恢复从上次 succeeded 节点之后继续
- **Human 节点挂起不占 worker**：24h 后确认仍可继续
- **失败节点单独重试**：不重跑全链
- **全部输入输出落 run_nodes**：与 ai_calls 追踪打通
