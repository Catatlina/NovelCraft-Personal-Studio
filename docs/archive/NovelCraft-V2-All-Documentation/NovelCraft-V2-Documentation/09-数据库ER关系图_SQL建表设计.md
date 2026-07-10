# NovelCraft V2.0 数据库ER关系图 + SQL建表设计

## 核心实体关系

用户 User

1:N

小说项目 Novel

1:N

章节 Chapter

1:N

章节版本 ChapterVersion

小说项目关系：

Novel ├── World ├── Character ├── StoryArc ├── Foreshadow ├──
KnowledgeBase └── PublishRecord

## 核心表设计

users - id - email - password_hash - role - created_at

novels - id - user_id - title - genre - status - target_words

characters - id - novel_id - name - profile - personality - arc

chapters - id - novel_id - chapter_no - title - content - summary

ai_tasks - id - novel_id - agent - task_type - status - result

## 索引设计

-   用户查询索引
-   小说状态索引
-   章节全文索引
-   向量检索索引

## SQL规范

要求： - PostgreSQL 16 - pgvector - UUID主键 - 时间字段统一UTC -
软删除设计
