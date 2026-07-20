# 星禾AI工作台 · Plugin规范

> 版本：V1.0 | 日期：2026-07-20 | 角色：软件架构师
>
> ⚠️ V1阶段Plugin系统为架构预留，实际开发在V2+。本文档定义接口和规范。

---

## 一、Plugin定义

Plugin是**扩展平台能力的第三方模块**。Plugin必须经过注册、权限申请、配置和生命周期管理。

---

## 二、Plugin类型

| 类型 | 说明 | 示例 |
|------|------|------|
| **datasource** | 新增数据源 | 豆瓣数据源、知乎热榜 |
| **publish** | 新增发布渠道 | 新小说平台、社交媒体 |
| **format** | 新增格式支持 | EPUB导出、LaTeX排版 |
| **provider** | 新增AI模型 | 本地模型、新云端模型 |
| **tool** | 通用工具 | 字数统计、查重、翻译 |
| **theme** | 界面主题 | 品牌定制主题 |

---

## 三、Plugin模型

```json
{
  "id": "plugin_douban_source",
  "slug": "douban_source",
  "name": "豆瓣数据源",
  "version": "1.0.0",
  "type": "datasource",
  "author": "社区开发者",
  "description": "接入豆瓣读书评分和评论数据",
  "icon": "https://...",
  "permissions": ["network:outbound", "storage:write"],
  "config_schema": {
    "type": "object",
    "properties": {
      "api_endpoint": {"type": "string", "default": "https://api.douban.com"},
      "rate_limit": {"type": "integer", "default": 10}
    }
  },
  "entry_point": "plugin/main.py",
  "min_platform_version": "1.0.0",
  "status": "active"
}
```

---

## 四、Plugin权限系统

| 权限 | 说明 | 风险等级 |
|------|------|----------|
| `network:outbound` | 外部网络请求 | 中 |
| `storage:read` | 读取用户数据 | 高 |
| `storage:write` | 写入用户数据 | 高 |
| `ai:call` | 调用AI Engine | 中 |
| `notification:send` | 发送通知 | 低 |
| `file:read` | 读取文件 | 高 |
| `file:write` | 写入文件 | 高 |

**禁止Plugin直接访问核心数据库。所有数据访问必须通过API。**

---

## 五、Plugin生命周期

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ REGISTER │ →  │ INSTALL  │ →  │ ACTIVATE │ →  │  UPDATE  │
│  注册     │    │  安装     │    │  激活     │    │  更新     │
└──────────┘    └──────────┘    └────┬─────┘    └──────────┘
                                     │
                              ┌──────┴─────┐
                              │ DEACTIVATE │ → ┌──────────┐
                              │  停用       │   │UNINSTALL │
                              └────────────┘   │  卸载     │
                                               └──────────┘
```

---

## 六、Plugin开发规范

### 6.1 Plugin结构

```
my-plugin/
├── plugin.json          # Plugin元数据
├── main.py              # 入口
├── requirements.txt     # 依赖
├── config_schema.json   # 配置Schema
├── README.md            # 文档
└── tests/               # 测试
```

### 6.2 Plugin沙箱

- Plugin运行在沙箱环境中
- 限制网络访问范围（白名单）
- 限制CPU/内存使用
- 限制文件系统访问路径

---

## 七、Plugin通信方式

Plugin通过标准API与平台通信：

```
Plugin → POST /api/v1/plugins/{id}/hooks/{event}
Platform → POST {plugin_webhook_url}/events/{type}
```

---

## 八、Plugin Marketplace（V3）

| 功能 | 说明 |
|------|------|
| 浏览/搜索 | 分类浏览，关键词搜索 |
| 一键安装 | 自动处理依赖和权限 |
| 版本管理 | 自动检测更新 |
| 评分评论 | 社区反馈 |
| 开发者中心 | 上传、管理、收益 |
| 安全审核 | 代码扫描 + 行为监控 |

---

## 九、禁止事项

| ❌ 禁止 | 说明 |
|--------|------|
| Plugin直接访问数据库 | 必须通过API |
| Plugin未声明权限 | 权限必须注册 |
| Plugin绕过AI Engine | AI调用必须走Engine |
| Plugin修改其他Plugin数据 | 严格隔离 |
| Plugin在V1实现完整市场 | 仅做架构预留 |
