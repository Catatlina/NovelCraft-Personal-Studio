# NovelCraft V2.0 Agent详细设计

## Agent架构

Agent Manager

统一调度：

Producer Story Architect Character Outline Writer Continuity Style
Editor Market Publisher

## Agent标准接口

Agent.run(context)

输入：

{ novel_context, task, constraints }

输出：

{ result, confidence, metadata }

## Context Hub

七层上下文：

1.  小说总纲
2.  世界观
3.  人物关系
4.  当前剧情
5.  最近章节
6.  伏笔状态
7.  用户要求

## 状态机

IDEA

↓

OUTLINE

↓

WORLD

↓

WRITING

↓

REVIEW

↓

PUBLISH

## Prompt管理

每个Agent：

-   System Prompt
-   Task Prompt
-   Style Prompt
-   Safety Prompt

支持： - 版本管理 - A/B测试 - 效果评分

## Writer Agent

负责：

-   场景生成
-   对话
-   描写
-   节奏控制

## Editor Agent

负责：

-   AI痕迹检测
-   文风优化
-   商业化修改
