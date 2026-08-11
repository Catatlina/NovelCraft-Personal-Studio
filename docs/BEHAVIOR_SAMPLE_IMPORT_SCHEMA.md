# 行为级黄金样本导入格式

知识条目使用 `kind: "behavior_sample"`，必须带项目级 `meta`。导入到哪个工作室项目由 API 的 `project_id` 决定；但一个工作室项目可以包含多本小说，因此还必须带 `source_novel_id`，检索时按小说再次隔离，不允许跨小说复用。

```json
[
  {
    "title": "场景功能-结果反馈",
    "kind": "behavior_sample",
    "body": "只写行为标注：人物目标、信息缺口、选择压力、因果推进、可见结果、代价和余波。不要复制原文。",
    "meta": {
      "behavior_annotation": "主角先做出主动选择；局部人物有独立目标和拒绝；信息通过动作和结果逐步获得；兑现同时改变状态并留下成本。",
      "scene_type": "对抗/调查/交易",
      "viewpoint": "限知视角",
      "pressure": "倒计时、暴露风险、资源不足",
      "result_type": "可见结果+新压力",
      "tags": ["主动选择", "信息缺口", "结果成本"],
      "source_project": "project-id",
      "source_novel_id": "novel-id",
      "source_file": "行为标注来源文件"
    }
  }
]
```

`source_project` 用于追溯来源，`source_novel_id` 用于生成时的小说级硬隔离。`body` 和 `behavior_annotation` 都不得放整章正文。每个样本只保留一个主要学习点；每次生成最多检索 2—3 个样本，样本是行为参考，不是硬性的句长、标点或段落比例。
