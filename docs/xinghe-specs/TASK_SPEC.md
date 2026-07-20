# 星禾AI工作台 · 任务系统规范

> 版本：V1.0 | 日期：2026-07-20 | 角色：后端架构师

---

## 一、任务系统定位

所有长耗时操作（>5秒）必须异步执行。任务系统负责：任务创建、队列调度、Worker执行、状态更新、结果保存。

---

## 二、任务生命周期

```
CREATED → QUEUED → RUNNING → COMPLETED
                    ↓
                  FAILED → RETRY → RUNNING
                    ↓
                  CANCELLED
```

| 状态 | 说明 |
|------|------|
| `created` | 任务已创建，等待入队 |
| `queued` | 已入队，等待Worker |
| `running` | Worker正在执行 |
| `waiting_human` | 等待人工确认 |
| `completed` | 执行完成 |
| `failed` | 执行失败（可重试） |
| `cancelled` | 用户取消 |
| `retry` | 重试中 |

---

## 三、任务类型

| 类型 | 说明 | 超时 | 重试 |
|------|------|------|------|
| `novel.bootstrap` | 自动成书 | 30min | 3次 |
| `novel.chapter_generate` | 章节生成 | 10min | 3次 |
| `novel.deai` | 去AI化 | 5min | 2次 |
| `ranking.scan` | 扫榜 | 10min | 2次 |
| `hotspot.collect` | 热点采集 | 5min | 1次 |
| `publish.execute` | 发布 | 5min | 3次 |
| `knowledge.embed` | 向量嵌入 | 3min | 1次 |
| `agent.run` | Agent运行 | 60min | 1次 |

---

## 四、任务数据结构

```json
{
  "task_id": "uuid",
  "type": "novel.chapter_generate",
  "status": "running",
  "user_id": "uuid",
  "project_id": "uuid",
  "novel_id": "uuid",
  "inputs": {
    "chapter_number": 5,
    "outline_id": "uuid"
  },
  "outputs": {
    "content_id": "uuid",
    "word_count": 3200
  },
  "progress": 65.0,
  "current_step": "writing_draft",
  "error": null,
  "retry_count": 0,
  "max_retries": 3,
  "created_at": "2026-07-20T10:00:00Z",
  "started_at": "2026-07-20T10:00:05Z",
  "completed_at": null
}
```

---

## 五、任务执行流程

```
1. 用户触发操作
   ↓
2. POST /api/v1/... 返回 {task_id, status: "queued"}
   ↓
3. Celery Worker 领取任务
   ↓
4. 更新状态 running
   ↓
5. 执行过程中通过 SSE/WebSocket 推送进度
   ↓
6. 完成 → 更新 completed，保存结果
   失败 → 判断是否重试
```

---

## 六、实时状态推送

任务状态变更通过WebSocket推送：

```json
{
  "type": "task.progress",
  "task_id": "uuid",
  "status": "running",
  "progress": 65.0,
  "current_step": "writing_draft",
  "message": "正在生成第5章..."
}
```

---

## 七、定时任务（Celery Beat）

| 任务 | 频率 | 说明 |
|------|------|------|
| `hotspot.collect_daily` | 每6小时 | 热点采集 |
| `daily_briefing` | 每天8:00 | 每日晨报 |
| `budget.reset_monthly` | 每月1日 | 预算重置 |
| `backup.daily` | 每天3:00 | 数据库备份 |

---

## 八、禁止事项

| ❌ 禁止 | ✅ 正确做法 |
|--------|-----------|
| 同步执行长任务 | Celery异步 + 实时状态推送 |
| 大量轮询任务状态 | WebSocket/SSE推送 |
| 任务无超时限制 | 每个任务类型必须设timeout |
| 任务无重试机制 | 定义max_retries + 退避策略 |
| 任务失败无通知 | 失败推送通知用户 |
