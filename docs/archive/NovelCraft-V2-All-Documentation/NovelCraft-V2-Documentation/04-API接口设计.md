# NovelCraft V2.0 API设计

## 用户接口

POST /auth/register POST /auth/login GET /auth/profile

## 小说接口

POST /novels GET /novels GET /novels/{id}

## AI生成

POST /novels/{id}/generate POST /novels/{id}/outline POST
/novels/{id}/chapter

## Agent

POST /agents/run GET /agents/status

## 审核

POST /review/chapter POST /rewrite

## 发布

POST /publish GET /publish/status
