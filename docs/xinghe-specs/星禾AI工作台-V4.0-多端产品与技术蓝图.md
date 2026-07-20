# 星禾AI工作台 V4.0 多端产品与技术蓝图

> **Xinghe AI Workspace — AI生产力操作系统**
>
> 版本：V4.0 | 日期：2026-07-20 | 状态：长期战略规划
>
> 编制角色：CPO · CTO · AI Agent架构师 · SaaS产品经理 · Web架构师 · Android架构师 · iOS架构师 · UI/UX设计总监
>
> ⚠️ **重要提示**：本文档是 **2-5年长期战略蓝图**。当前阶段（V1）的执行文档在 `/docs/` 目录下。请优先阅读 `/docs/ROADMAP.md` 了解近期开发计划。不要按照本文档的全部内容一次性开发。

---

## 目录

1. [产品定位](#一产品定位)
2. [Web规划](#二web规划)
3. [移动Web规划](#三移动web规划)
4. [Android规划](#四android规划)
5. [iOS规划](#五ios规划)
6. [UI设计规范](#六ui设计规范)
7. [Design Token](#七design-token)
8. [组件体系](#八组件体系)
9. [技术架构](#九技术架构)
10. [API设计](#十api设计)
11. [数据同步](#十一数据同步)
12. [Skill体系](#十二skill体系)
13. [Agent体系](#十三agent体系)
14. [Plugin体系](#十四plugin体系)
15. [SaaS商业化](#十五saas商业化)
16. [开发路线](#十六开发路线)
17. [风险分析](#十七风险分析)

---

## 一、产品定位

### 1.1 产品愿景

**星禾AI工作台（Xinghe AI Workspace）** 不是一个单一的AI工具，而是一个 **AI生产力操作系统**。

当前阶段以 **小说创作** 作为第一个深度AI应用（基于现有 NovelCraft Personal Studio V2.2 能力），但架构设计上必须支持未来扩展为覆盖全内容创作场景的平台。

### 1.2 产品定位矩阵

| 维度 | 定位 |
|------|------|
| **品类** | AI原生生产力操作系统 |
| **核心用户** | 重度内容创作者（小说作者 → 自媒体作者 → 知识工作者） |
| **对标参考** | ChatGPT + Claude + Cursor + Notion + Dify 的融合体 |
| **差异化** | 不是对话工具，是完整创作工作流 + Skill/Agent/Plugin 生态 |
| **商业模式** | SaaS订阅（免费/Pro/团队/企业） |
| **技术壁垒** | AI Engine统一调度 + 扫榜成书闭环 + 去AI化流水线 + 多端实时同步 |

### 1.3 现有资产盘点（来自 NovelCraft V2.2）

| 资产类别 | 详情 | 保留策略 |
|----------|------|----------|
| **后端** | FastAPI + PostgreSQL(26+表) + Celery/Redis + 15个服务模块 | 完整保留，渐进升级 |
| **前端** | React 19 + TypeScript + Vite，29组件，129条后端路由 | 保留核心，重写基座 |
| **AI能力** | DeepSeek/Claude/OpenAI/Gemini 四Provider，BYOK安全模型 | 完整保留，统一AI Engine |
| **核心功能** | 扫榜→分析→选题→生成→审核→发布 全链路 | 作为小说App保留 |
| **设计系统** | doc12完整Design Token，暗色优先，对标Linear/Notion/Raycast | 保留并扩展多端Token |
| **测试** | 后端493+ passed，前端9/9 passed，Playwright E2E | 保持门禁 |
| **安全** | JWT + Fernet加密 + SAST CI + 密钥不落库 | 保持并增强移动端 |

### 1.4 产品架构全景图

```
┌─────────────────────────────────────────────────────────────────┐
│                    星禾AI工作台 (Xinghe AI Workspace)               │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                      应用层 (Apps)                           │ │
│  │  小说创作  │  文章创作  │  视频脚本  │  运营助手  │  ...     │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                     核心层 (Core)                            │ │
│  │  AI Engine  │ Workflow  │ Memory  │ Knowledge  │ User/Auth   │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    扩展层 (Extensions)                       │ │
│  │  Skill Center  │  Agent Center  │  Plugin Marketplace        │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    客户端层 (Clients)                         │ │
│  │  PC Web  │  移动Web(PWA)  │  Android App  │  iOS App         │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、Web规划

### 2.1 PC Web定位

**专业AI生产力工作站** — 面向重度创作者的全功能工作环境。

### 2.2 布局架构

采用三栏工作台布局（现有设计系统已定义）：

```
┌──────────┬──────────────────────────────────┬──────────────┐
│  导航栏   │                                  │              │
│ (220px)  │         主工作区                  │  AI Copilot  │
│          │                                  │  (320px)     │
│  · 工作台 │    编辑器 / 矩阵 / 看板            │              │
│  · 小说   │                                  │  · AI对话     │
│  · 扫榜   │                                  │  · 上下文面板  │
│  · 书库   │                                  │  · Agent状态  │
│  · 热点   │                                  │  · 快捷操作    │
│  · 知识库 │                                  │              │
│  · 发布   │                                  │              │
│  · 设置   │                                  │              │
└──────────┴──────────────────────────────────┴──────────────┘
                      顶栏(48px): 面包屑 · ⌘K · 主题 · 头像
```

### 2.3 核心能力升级

| 能力域 | 当前状态 | V4.0目标 |
|--------|---------|----------|
| **设计系统** | doc12 Token已定义，部分组件未对齐 | 全组件对齐Token，禁止裸色值 |
| **三屏工作台** | Dashboard/Overview/Workspace stub | 真实数据驱动的工作台首页 |
| **命令面板** | ⌘K已实现 | 扩展为全局动作入口，含AI命令 |
| **编辑器** | Tiptap + novel-prose | 增强AI浮条，行内批注，版本树 |
| **多窗口** | 不支持 | 支持多Tab/多面板拖拽布局 |
| **快捷键** | 已定义5组 | 扩展为完整键盘地图 |
| **主题** | Dark/Light双模式 | 保持，增加品牌色自定义 |
| **响应式** | 断点已定义(sm/md/lg/xl/2xl) | 完善三栏→双栏→单栏自适应 |

### 2.4 页面体系

基于现有19个Tab，重组为模块化结构：

```
Pages/
├── Workspace/          # 工作台首页（数据概览 + 快捷入口）
├── NovelApp/           # 小说创作模块
│   ├── RankingCenter   # 扫榜中心
│   ├── BookLibrary     # 书库
│   ├── CreationWizard  # 创作向导
│   ├── Progress        # 生成进度
│   ├── Review          # 审阅
│   ├── Editor          # 编辑器
│   └── Foreshadowing   # 伏笔面板
├── ContentApp/         # 内容运营模块
│   ├── HotspotDashboard # 热点
│   ├── KnowledgeBrowser # 知识库
│   ├── FanoutMatrix    # 分发矩阵
│   └── PublishDashboard # 发布
├── StudioApp/          # 工作室模块
│   ├── Collaboration   # 协作
│   ├── AgentConsole    # 智能体
│   ├── PromptLab       # Prompt实验室
│   └── Costs           # 成本追踪
└── Settings/           # 设置
    ├── Providers       # AI配置
    ├── Connections     # 平台连接
    ├── Members         # 成员管理
    └── Billing         # 账单
```

---

## 三、移动Web规划

### 3.1 移动Web定位

**轻量访问入口** — 不是PC的缩小版，而是移动优先的独立设计。

### 3.2 设计原则

| 原则 | 说明 |
|------|------|
| **移动优先** | 从移动场景出发设计，非PC降级 |
| **一屏一任务** | 每屏聚焦一个核心操作 |
| **触控优先** | 触控目标≥44px，手势操作 |
| **轻量快速** | 首屏<3秒，PWA离线可用 |
| **核心功能** | 查看 > 管理 > 轻量创作 |

### 3.3 信息架构

```
底部导航 (Bottom Tab Bar)
├── 首页      # 今日任务 + AI推荐 + 最近项目 + 快捷创建
├── AI助手    # 对话式AI交互（类ChatGPT）
├── 项目      # 小说/文章项目列表
├── 任务      # Agent执行状态 + 生成记录 + 通知
└── 我的      # 设置/模型/账户/会员
```

### 3.4 功能范围

| 功能 | 支持 | 说明 |
|------|------|------|
| 查看项目 | ✅ | 小说列表、章节浏览 |
| AI对话 | ✅ | 流式SSE，支持文本输入 |
| 查看进度 | ✅ | Agent/生成任务状态 |
| 接收通知 | ✅ | 任务完成、热点发现 |
| 快速生成 | ✅ | 调用Skill生成标题/摘要 |
| 查看热点 | ✅ | 热点列表、趋势查看 |
| 项目管理 | ⚠️ | 创建/删除/归档（简化版） |
| 编辑器 | ❌ | 复杂编辑回PC |
| 扫榜分析 | ❌ | 复杂分析回PC |
| 发布管理 | ❌ | 查看状态，操作回PC |

### 3.5 PWA策略

| 层级 | 能力 | 说明 |
|------|------|------|
| **L1 Shell** | 静态资源缓存 | 已实现 sw.js，离线展示基础UI |
| **L2 内容** | 关键数据缓存 | IndexedDB存储最近项目、章节内容 |
| **L3 离线队列** | 离线操作队列 | 离线时的AI请求/编辑操作排队，上线同步 |

---

## 四、Android规划

### 4.1 技术选型分析

#### 方案对比矩阵

| 维度 | React Native (Expo) | Flutter | Kotlin Multiplatform |
|------|---------------------|---------|----------------------|
| **编程语言** | JavaScript/TypeScript | Dart | Kotlin + Swift |
| **UI渲染** | 原生组件（JSI桥接） | 自绘引擎Impeller | 原生SwiftUI+Compose |
| **代码复用率** | 85-95% | 85-95% | 40-60% |
| **性能** | 良好（New Architecture） | 优秀（接近原生） | 原生级 |
| **冷启动** | 中等 | 中等 | 最快 |
| **内存占用** | 中等 | 较高 | 最低 |
| **人才市场** | 最大（JS/TS开发者） | 中等增长中 | 最小（需双平台专家） |
| **Web代码复用** | 高（共享React模式/TypeScript） | 无（Dart独立） | 无 |
| **生态系统** | npm + Expo SDK 52 | pub.dev | JVM + KMP生态 |
| **维护成本** | 中等（已显著降低） | 最低 | 较高（双原生UI） |
| **iOS复用** | 直接复用 | 直接复用 | 需独立SwiftUI层 |
| **团队适配** | 现有React前端团队直接转型 | 需学习Dart | 需招聘原生工程师 |

#### 关键技术趋势（2026）

- **React Native**：New Architecture (JSI+Fabric+TurboModules) 自0.76起成熟，Expo SDK 52是推荐起点，性能已大幅提升
- **Flutter**：Impeller渲染器在iOS和Android默认启用，像素级一致性最强，Dart 3.x稳定
- **KMP**：Compose Multiplatform将Compose UI扩展到iOS，但成熟度仍不如RN/Flutter

#### 核心决策因素

本项目有 **React 19 + TypeScript** 前端团队和现有代码库。考虑：

1. **代码复用**：React Native可复用现有TypeScript类型定义、API客户端逻辑、业务常量、Design Token
2. **团队效率**：现有React开发者可直接贡献移动端，无需学习Dart或招聘原生团队
3. **AI流式体验**：React Native对SSE/WebSocket支持成熟
4. **长期维护**：一套JS/TS技术栈覆盖Web+移动端，降低维护成本

#### 🏆 推荐方案：React Native (Expo SDK 52)

**理由**：

> 项目已有React 19 + TypeScript技术栈和设计系统。React Native + Expo可实现85%+代码复用（API层、类型定义、状态管理逻辑、Design Token），前端团队成员可直接贡献移动端。Flutter虽性能略优，但引入Dart语言会导致技术栈分裂。KMP需维护两套原生UI，不适合以Web为主的团队。

**架构**：

```
shared/                    # 跨端共享包
├── types/                 # TypeScript类型定义（Web + Mobile共享）
├── api/                   # API客户端（Web + Mobile共享）
├── tokens/                # Design Token（Web + Mobile共享）
└── utils/                 # 工具函数

apps/
├── web/                   # React 19 + Vite（现有）
└── mobile/                # React Native + Expo SDK 52（新建）
    ├── screens/           # 移动端页面
    ├── components/        # 移动端原生组件
    ├── navigation/        # React Navigation
    └── native/            # 原生模块（推送、生物识别、相机）
```

### 4.2 Android App定位

**移动AI创作助手** — 随时随地调用AI、查看进度、管理项目、接收结果。

### 4.3 核心场景

| 场景 | 说明 | 优先级 |
|------|------|--------|
| 随时调用AI | 类ChatGPT对话，支持文本/语音/图片 | P0 |
| 查看创作进度 | 实时查看Agent/生成任务状态 | P0 |
| 管理项目 | 创建/查看/管理小说和文章项目 | P0 |
| 接收Agent结果 | 任务完成推送通知 | P0 |
| 快速生成内容 | 一键调用Skill（标题/摘要/续写） | P1 |
| 查看热点 | 热点趋势、每日晨报 | P1 |
| 语音输入 | 语音转文字创作 | P2 |
| 拍照上传 | 拍照上传资料到知识库 | P2 |

### 4.4 信息架构

```
底部导航（5个Tab）
│
├── 🏠 首页
│   ├── 今日任务卡片
│   ├── AI推荐列表
│   ├── 最近项目（横向滚动）
│   └── 快捷创建 FAB
│
├── 💬 AI助手
│   ├── 对话列表
│   ├── 聊天界面（SSE流式）
│   ├── 文件/图片上传
│   └── 语音输入按钮
│
├── 📁 项目
│   ├── 项目分类Tab（小说/文章/知识库）
│   ├── 项目卡片列表
│   ├── 项目详情
│   └── 搜索/筛选
│
├── 📋 任务
│   ├── 运行中/已完成/失败 分类
│   ├── Agent执行状态
│   ├── 生成记录时间线
│   └── 通知列表
│
└── 👤 我的
    ├── 账户信息
    ├── AI模型配置
    ├── 会员/订阅
    ├── 设备管理
    ├── 设置
    └── 关于
```

### 4.5 移动端特有能力

| 能力 | 实现方案 |
|------|----------|
| **推送通知** | FCM + 国产厂商推送（华为/小米/OPPO/VIVO） |
| **语音输入** | 系统语音识别API + 实时转文字 |
| **生物识别** | BiometricPrompt API（指纹/面部） |
| **文件上传** | Document Picker + Camera Capture |
| **离线模式** | SQLite本地存储 + 操作队列 |
| **分享** | Android Sharesheet + 深度链接 |
| **后台任务** | WorkManager定期同步Agent状态 |

### 4.6 移动端AI交互设计

```
┌─────────────────────────────────┐
│  ← AI助手                       │
│                                 │
│  ┌─────────────────────────────┐│
│  │ 🤖 你好，我是星禾AI助手      ││
│  │ 可以帮你：                   ││
│  │ · 分析小说市场趋势           ││
│  │ · 生成爆款标题               ││
│  │ · 续写章节内容               ││
│  │ · 检查文章AI味道             ││
│  └─────────────────────────────┘│
│                                 │
│  ┌─────────────────────────────┐│
│  │ 用户：帮我分析一下最近番茄   ││
│  │ 小说榜单的热门趋势           ││
│  └─────────────────────────────┘│
│                                 │
│  ┌─────────────────────────────┐│
│  │ 🤖 正在分析中... [流式输出]  ││
│  │                             ││
│  └─────────────────────────────┘│
│                                 │
│  ┌─────────────────────────────┐│
│  │ [快速操作]                   ││
│  │ [生成标题] [续写] [去AI味]   ││
│  └─────────────────────────────┘│
│                                 │
│  ┌─────────────────────────────┐│
│  │ 🎤 语音  ⌂ 文件  📷 拍照    ││
│  │ [________________] 发送 →   ││
│  └─────────────────────────────┘│
└─────────────────────────────────┘
```

---

## 五、iOS规划

### 5.1 iOS定位

**与Android功能对等** — 复用React Native代码库，保持功能一致，遵循iOS设计规范。

### 5.2 技术方案

基于React Native方案，iOS端直接复用移动端代码：

```
apps/mobile/
├── screens/           # 共享页面（Android + iOS）
├── components/        # 共享组件（Android + iOS）
├── navigation/        # React Navigation
└── native/
    ├── android/       # Android原生模块
    └── ios/           # iOS原生模块
        ├── PushNotification  # APNs
        ├── BiometricAuth      # Face ID / Touch ID
        └── ShareExtension    # iOS分享扩展
```

### 5.3 iOS特有能力

| 能力 | 实现方案 |
|------|----------|
| **推送通知** | APNs |
| **生物识别** | Face ID / Touch ID (LocalAuthentication) |
| **Widget** | iOS Widget (SwiftUI) |
| **Siri Shortcuts** | 快捷指令集成 |
| **iCloud同步** | 可选：偏好设置跨设备同步 |
| **Handoff** | Mac与iOS间任务接力 |

### 5.4 iOS设计适配

| 适配点 | 说明 |
|--------|------|
| **导航** | 遵循iOS HIG，支持大标题 + 滑动返回手势 |
| **字体** | SF Pro Display/Text 系统字体 |
| **圆角** | iOS系统圆角（与Android差异由Design Token处理） |
| **触觉反馈** | UIFeedbackGenerator |
| **安全区域** | SafeArea适配（刘海屏/灵动岛） |
| **深色模式** | 跟随系统 + 手动切换 |

### 5.5 开发优先级

iOS开发安排在 **Phase 4**，在Android验证移动端方案后启动。此时：
- 85%+ 代码已由Android验证
- 仅需适配iOS原生模块和设计细节
- 预计开发周期为Android的30-40%

---

## 六、UI设计规范

### 6.1 设计价值观

| 原则 | 说明 |
|------|------|
| **Calm by default** | 默认安静，低饱和中性底，高亮只给"此刻重要的事" |
| **Dense but breathe** | 高密度 + 规律留白 |
| **Keyboard is first-class** | 每个动作有快捷键（Web），移动端手势优先 |
| **Dark-native** | 暗色为原生默认，亮色是变体而非补丁 |
| **Motion with restraint** | 动效克制，≤200ms（Web），遵循平台规范（移动端） |
| **Mobile-first for mobile** | 移动端不是缩小PC，是独立设计 |

### 6.2 对标参考

| 维度 | PC Web | 移动端 |
|------|--------|--------|
| **信息密度** | Linear — 紧凑表格/列表 | Apple Notes — 清晰卡片 |
| **编辑沉浸** | Notion/Cursor — AI浮条/内联 | ChatGPT App — 对话式交互 |
| **命令交互** | Raycast — ⌘K全局命令 | iOS Spotlight — 下拉搜索 |
| **视觉风格** | Linear/Notion — 极简暗色 | Apple/ChatGPT — 干净明亮 |
| **动效** | Framer Motion — 微交互 | 平台原生动效 |

### 6.3 跨端设计原则

| 原则 | 说明 |
|------|------|
| **品牌一致** | 颜色、Logo、品牌识别统一 |
| **布局自适应** | PC三栏 → 平板双栏 → 手机单栏 |
| **组件对应** | 同一功能在各端使用对应原生组件 |
| **交互适配** | PC键盘快捷键 ↔ 移动端手势 |
| **内容优先** | 内容结构一致，展示形式适配端 |

### 6.4 设计验收规范

所有UI实现必须通过以下验收：

1. **Token合规**：只用Design Token，禁裸色值（stylelint/eslint守卫）
2. **双模式**：明暗双模式截图验证
3. **三态齐全**：空态/加载态/错误态
4. **键盘可达**（Web）：焦点环 + Tab可达
5. **触控可达**（移动端）：触控目标≥44px
6. **对标自评**：与对标产品并排对比

---

## 七、Design Token

### 7.1 Token体系架构

```
Design Tokens
├── Brand Tokens (品牌级)       # 跨端共享
│   ├── Color Palette
│   ├── Typography Scale
│   └── Brand Assets
├── Platform Tokens (平台级)    # 端特有
│   ├── Web (CSS Custom Properties)
│   ├── Android (XML Resources)
│   └── iOS (Swift Asset Catalog)
└── Component Tokens (组件级)   # 组件映射
    ├── Button
    ├── Card
    ├── Input
    └── ...
```

### 7.2 品牌色彩Token（跨端共享）

#### 主色系（Indigo 低饱和靛蓝）

| Token | Dark HEX | Light HEX | 用途 |
|-------|----------|-----------|------|
| `--brand-50` | #EEF0FE | #F1F3FE | 极浅底 |
| `--brand-100` | #D9DEF9 | #DCE2FB | 浅底/hover |
| `--brand-300` | #838DEB | #7884E0 | 弱强调 |
| `--brand-500` | #5B66DB | #4F5BD6 | 主色/主按钮 |
| `--brand-600` | #444FCB | #3E48C2 | 主色按压 |
| `--brand-700` | #373FA8 | #313A9E | 深强调 |
| `--brand-foreground` | #FFFFFF | #FFFFFF | 主色上文字 |

#### 中性色

| Token | Dark HEX | Light HEX | 用途 |
|-------|----------|-----------|------|
| `--bg-base` | #14161C | #FFFFFF | 页面底 |
| `--bg-subtle` | #1C1F26 | #F6F7F9 | 次级底/卡片 |
| `--bg-muted` | #252932 | #EDEFF2 | 弱底/悬浮 |
| `--bg-elevated` | #2C313B | #FFFFFF | 弹层/浮条 |
| `--border-subtle` | #363C47 | #E0E3E8 | 细分隔线 |
| `--border-strong` | #49515F | #C2C7D0 | 强边框/focus |
| `--text-primary` | #E8EAF0 | #1E2230 | 主文字 |
| `--text-secondary` | #A6ABBA | #595F70 | 次文字 |
| `--text-muted` | #797F8E | #868D9C | 弱文字/占位 |

#### 语义色

| Token | Dark HEX | Light HEX | 用途 |
|-------|----------|-----------|------|
| `--success` | #31B572 | #2C9C62 | 通过/成功 |
| `--warning` | #F2A93B | #D98E1F | 风险/警告 |
| `--danger` | #DE4B5E | #CC3B4E | 错误/拦截 |
| `--info` | #2E9BD6 | #1878B8 | 信息/提示 |

### 7.3 字体Token

#### Web端

| Token | 字号/行高 | 用途 |
|-------|-----------|------|
| `--text-xs` | 11px/16px | 标签/脚注 |
| `--text-sm` | 12px/18px | 次要信息/表格 |
| `--text-base` | 14px/21px | 正文 |
| `--text-md` | 16px/24px | 小标题 |
| `--text-lg` | 19px/28px | 区块标题 |
| `--text-xl` | 23px/32px | 页标题 |
| `--text-2xl` | 28px/36px | 大标题 |
| `--editor-text` | 16px/1.8 | 编辑器正文 |

#### 移动端

| Token | iOS (SF Pro) | Android (Roboto) | 用途 |
|-------|-------------|-------------------|------|
| `caption` | 12pt | 12sp | 说明文字 |
| `body` | 17pt | 16sp | 正文 |
| `headline` | 17pt Semibold | 16sp Medium | 列表标题 |
| `title` | 20pt Bold | 20sp Bold | 页面标题 |
| `large-title` | 34pt Bold | 28sp Bold | 首页大标题 |

### 7.4 间距Token

| Token | 值 | Web | 移动端 |
|-------|-----|-----|--------|
| `--space-1` | 4px | icon间隙 | 紧凑间隙 |
| `--space-2` | 8px | 组内间距 | 列表项内 |
| `--space-3` | 12px | 控件内边距 | 卡片内边距 |
| `--space-4` | 16px | 卡片内边距 | 页面边距 |
| `--space-6` | 24px | 面板内边距 | 区块间距 |
| `--space-8` | 32px | 区块间距 | 大区块 |
| `--space-12` | 48px | 页级留白 | 极少用 |

### 7.5 圆角Token

| Token | 值 | 用途 |
|-------|-----|------|
| `--radius-sm` | 4px | 标签/小控件 |
| `--radius-md` | 6px(Web)/8px(移动端) | 按钮/输入/卡片 |
| `--radius-lg` | 10px(Web)/12px(移动端) | 浮层/弹窗 |
| `--radius-xl` | 14px(Web)/16px(移动端) | 大弹窗 |
| `--radius-full` | 9999px | 头像/胶囊 |

### 7.6 阴影Token

| Token | Web | 移动端(Android) | 移动端(iOS) |
|-------|-----|-----------------|-------------|
| `--shadow-sm` | 0 1px 3px rgba(0,0,0,.08) | elevation 2dp | 浅模糊阴影 |
| `--shadow-md` | 0 4px 12px rgba(0,0,0,.10) | elevation 4dp | 中模糊阴影 |
| `--shadow-lg` | 0 12px 32px rgba(0,0,0,.14) | elevation 8dp | 深模糊阴影 |

### 7.7 动效Token

| Token | Web | 移动端 |
|-------|-----|--------|
| `--dur-fast` | 120ms | 150ms |
| `--dur-base` | 180ms | 225ms |
| `--dur-slow` | 260ms | 300ms |
| `--ease-standard` | cubic-bezier(0.2,0,0,1) | 平台默认缓动 |

---

## 八、组件体系

### 8.1 组件分层

```
Component Architecture
│
├── Core Components (核心组件)        # 跨端共享概念，各端原生实现
│   ├── Button
│   ├── Input / TextField
│   ├── Card
│   ├── List / ListItem
│   ├── Dialog / Modal / BottomSheet
│   ├── Toast / Snackbar
│   ├── Badge / Tag
│   ├── Avatar
│   ├── Skeleton
│   └── EmptyState
│
├── AI Components (AI专用组件)
│   ├── AIChat / ChatBubble
│   ├── AIMessage (流式输出)
│   ├── AIFloatingBar (AI浮条)
│   ├── StreamingText
│   └── SkillQuickAction
│
├── Business Components (业务组件)
│   ├── ProjectCard
│   ├── TaskCard / TaskTimeline
│   ├── NovelChapterList
│   ├── RankingTable / RankingCard
│   ├── HotspotCard
│   ├── KnowledgeItem
│   ├── ProgressTracker
│   └── CostChart
│
└── Layout Components (布局组件)
    ├── AppShell (三栏布局)
    ├── MobileTabBar (底部导航)
    ├── CommandPalette (⌘K)
    ├── Sidebar
    └── PageHeader
```

### 8.2 跨端组件映射

| 功能概念 | Web | Android | iOS |
|----------|-----|---------|-----|
| 按钮 | `<Button variant="primary">` | `MaterialButton` | `UIButton` (filled) |
| 输入框 | `<Input>` | `TextInputLayout` | `UITextField` |
| 卡片 | `<Card>` | `MaterialCardView` | `UICardView` |
| 列表 | `<DataTable>` / `<List>` | `RecyclerView` | `UITableView` / `List` |
| 弹窗 | `<Dialog>` | `AlertDialog` | `UIAlertController` |
| 底部菜单 | — | `BottomSheet` | `UISheetPresentation` |
| 轻提示 | `<Toast>` | `Snackbar` | 自定义Toast |
| 空状态 | `<EmptyState>` | `EmptyStateView` | `EmptyStateView` |
| 骨架屏 | `<Skeleton>` | `ShimmerLayout` | `ShimmerView` |
| AI对话 | `<AIChat>` | `ChatRecyclerView` | `ChatCollectionView` |

### 8.3 组件开发规范

1. **概念统一**：同一功能在各端使用相同的组件名和Props概念
2. **原生实现**：各端使用最适合的原生组件实现
3. **Token驱动**：所有视觉属性从Design Token获取
4. **状态覆盖**：每个组件必须有 loading/empty/error/success 四态
5. **可访问性**：Web关注ARIA，移动端关注Accessibility API

---

## 九、技术架构

### 9.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client Layer                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │  PC Web  │  │ 移动Web   │  │ Android  │  │   iOS    │        │
│  │ React 19 │  │ React 19 │  │ RN+Expo  │  │ RN+Expo  │        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
│       │              │              │              │              │
│       └──────────────┴──────────────┴──────────────┘              │
│                          │  HTTP/SSE/WS                          │
├──────────────────────────┼───────────────────────────────────────┤
│                     API Gateway (Nginx)                          │
├──────────────────────────┼───────────────────────────────────────┤
│                   Backend Layer (FastAPI)                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ Auth     │  │ AI Engine│  │ Workflow │  │ Knowledge│        │
│  │ JWT+OAuth│  │ Provider │  │  Engine  │  │  System  │        │
│  └──────────┘  │  Gateway │  └──────────┘  └──────────┘        │
│                └──────────┘                                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ Memory   │  │ Skill    │  │ Agent    │  │ Plugin   │        │
│  │ System   │  │ Manager  │  │ Manager  │  │ Manager  │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
├──────────────────────────────────────────────────────────────────┤
│                      Data Layer                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │PostgreSQL│  │  Redis   │  │ Celery   │  │  Vector  │        │
│  │ (主数据库) │  │(缓存/队列)│  │(任务队列) │  │  Store   │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
└──────────────────────────────────────────────────────────────────┘
```

### 9.2 后端架构（模块化单体）

```
backend/
├── app/
│   ├── core/                    # 核心基础设施
│   │   ├── config.py            # 配置管理
│   │   ├── security.py          # 安全（JWT/BYOK）
│   │   ├── authz.py             # 统一鉴权
│   │   ├── retry.py             # 重试策略
│   │   ├── circuit_breaker.py   # 断路器
│   │   ├── context_budget.py    # Token预算
│   │   └── concurrency.py       # 并发控制
│   │
│   ├── engine/                  # 🆕 AI Engine（统一AI调度）
│   │   ├── router.py            # AI调用统一入口
│   │   ├── provider_manager.py  # Provider管理
│   │   ├── prompt_registry.py   # Prompt注册表
│   │   ├── context_manager.py   # 上下文管理
│   │   ├── token_tracker.py     # Token/成本统计
│   │   └── model_router.py      # 模型路由
│   │
│   ├── modules/                 # 🆕 业务模块（模块化组织）
│   │   ├── novel/               # 小说模块
│   │   │   ├── api/             # REST端点
│   │   │   ├── services/        # 业务逻辑
│   │   │   ├── models/          # 数据模型
│   │   │   └── skills/          # 小说Skills
│   │   ├── content/             # 内容模块（文章等）
│   │   ├── hotspot/             # 热点模块
│   │   ├── knowledge/           # 知识库模块
│   │   ├── publish/             # 发布模块
│   │   ├── collaboration/       # 协作模块
│   │   └── analytics/           # 分析模块
│   │
│   ├── platform/                # 🆕 平台能力
│   │   ├── skill_manager.py     # Skill生命周期
│   │   ├── agent_manager.py     # Agent编排
│   │   ├── plugin_manager.py    # Plugin市场
│   │   └── workflow_engine.py   # 工作流引擎
│   │
│   ├── api/v1/                  # API路由
│   └── workers/                 # Celery任务
│
├── alembic/                     # 数据库迁移
├── tests/                       # 测试
└── requirements.txt
```

### 9.3 AI Engine设计

现有项目已有AI调用能力，V4.0将其统一为 **AI Engine**：

```
┌─────────────────────────────────────────────────────────┐
│                      AI Engine                           │
│                                                         │
│  调用方 (任何模块)                                        │
│       │                                                 │
│       ▼                                                 │
│  ┌─────────────┐                                        │
│  │ Model Router │  根据任务类型/成本/可用性路由模型        │
│  └──────┬──────┘                                        │
│         │                                               │
│  ┌──────▼──────┐                                        │
│  │Prompt Registry│  管理所有Prompt模板（版本化）           │
│  └──────┬──────┘                                        │
│         │                                               │
│  ┌──────▼──────┐                                        │
│  │Context Manager│  上下文装配 + Token预算控制             │
│  └──────┬──────┘                                        │
│         │                                               │
│  ┌──────▼──────┐                                        │
│  │Provider Gateway│  DeepSeek/Claude/OpenAI/Gemini       │
│  │  · 重试/退避  · 断路器  · 并发控制  · 超时管理        │
│  └──────┬──────┘                                        │
│         │                                               │
│  ┌──────▼──────┐                                        │
│  │Token Tracker │  Token使用 + 成本统计 + 预算校验        │
│  └─────────────┘                                        │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 9.4 前端架构

```
frontend/
├── packages/
│   ├── shared/                  # 🆕 跨端共享包
│   │   ├── types/               # TypeScript类型
│   │   ├── api/                 # API客户端
│   │   ├── tokens/              # Design Token定义
│   │   ├── hooks/               # 共享Hooks
│   │   └── utils/               # 工具函数
│   │
│   ├── web/                     # Web应用（现有重构）
│   │   ├── design/              # 设计系统
│   │   ├── components/          # 组件
│   │   ├── pages/               # 页面
│   │   ├── hooks/               # Web专用Hooks
│   │   └── lib/                 # Web工具
│   │
│   └── mobile/                  # 🆕 React Native应用
│       ├── screens/             # 页面
│       ├── components/          # 原生组件
│       ├── navigation/          # 导航
│       ├── hooks/               # 移动端Hooks
│       └── native/              # 原生模块
```

### 9.5 技术栈总览

| 层级 | 技术 | 说明 |
|------|------|------|
| **后端框架** | FastAPI (Python 3.11+) | 现有，保持 |
| **数据库** | PostgreSQL + pgvector | 现有，保持 |
| **缓存/队列** | Redis | 现有，保持 |
| **任务队列** | Celery + Beat | 现有，保持 |
| **Web前端** | React 19 + TypeScript + Vite | 现有，渐进升级 |
| **移动框架** | React Native + Expo SDK 52 | 🆕 |
| **状态管理** | React Context + Hooks | 现有方案，保持 |
| **UI组件(Web)** | Radix/shadcn定制 | 现有，保持 |
| **编辑器** | Tiptap | 现有，保持 |
| **样式方案** | CSS Custom Properties (Design Token) | 现有，保持 |
| **API通信** | REST + SSE + WebSocket | 现有，增强移动端 |
| **认证** | JWT + BYOK | 现有，增强移动端安全 |
| **容器化** | Docker Compose | 现有，保持 |
| **CI/CD** | GitHub Actions | 现有，扩展移动端 |

---

## 十、API设计

### 10.1 API设计原则

| 原则 | 说明 |
|------|------|
| **Backend First** | 后端API先于客户端设计 |
| **API First** | OpenAPI 3.1 作为唯一契约源 |
| **版本化** | URL路径版本 `/api/v1/` |
| **统一信封** | `{code, message, data}` 统一响应格式 |
| **分页标准** | `limit`/`offset`，默认limit=50 |
| **幂等性** | 写操作带 `Idempotency-Key` |
| **流式优先** | AI调用默认使用SSE流式返回 |

### 10.2 API路由体系

```
/api/v1/
├── /auth/                    # 认证
│   ├── POST /register
│   ├── POST /login
│   ├── POST /refresh
│   ├── GET  /me
│   └── POST /logout
│
├── /projects/                # 项目管理
│   ├── GET    /              # 项目列表
│   ├── POST   /              # 创建项目
│   ├── GET    /{id}          # 项目详情
│   ├── PUT    /{id}          # 更新项目
│   ├── DELETE /{id}          # 删除项目
│   └── POST   /{id}/novels   # 创建小说
│
├── /novels/                  # 小说（现有，保留）
│   ├── GET    /{id}
│   ├── POST   /{id}/bootstrap
│   ├── POST   /{id}/continue
│   └── ...
│
├── /contents/                # 内容（现有，保留）
│   ├── GET    /{id}
│   ├── POST   /{id}/ai/{op}
│   └── ...
│
├── /ranking/                 # 扫榜（现有，保留）
├── /library/                 # 书库（现有，保留）
├── /runs/                    # 工作流运行（现有，保留）
├── /knowledge/               # 知识库（现有，保留）
├── /hotspots/                # 热点（现有，保留）
├── /publish/                 # 发布（现有，保留）
│
├── /engine/                  # 🆕 AI Engine
│   ├── POST /chat            # 通用AI对话（SSE）
│   ├── POST /complete        # 通用AI补全（SSE）
│   ├── GET  /models          # 可用模型列表
│   └── GET  /usage           # Token使用统计
│
├── /skills/                  # 🆕 Skill中心
│   ├── GET    /              # Skill列表
│   ├── GET    /{id}          # Skill详情
│   ├── POST   /{id}/install  # 安装Skill
│   ├── POST   /{id}/execute  # 执行Skill
│   ├── PUT    /{id}/toggle   # 启用/禁用
│   └── DELETE /{id}          # 卸载
│
├── /agents/                  # 🆕 Agent中心
│   ├── GET    /              # Agent列表
│   ├── POST   /              # 创建Agent
│   ├── GET    /{id}          # Agent详情
│   ├── POST   /{id}/run      # 运行Agent
│   ├── GET    /{id}/runs     # Agent运行历史
│   └── PUT    /{id}          # 更新Agent
│
├── /plugins/                 # 🆕 Plugin市场
│   ├── GET    /              # Plugin列表
│   ├── GET    /{id}          # Plugin详情
│   ├── POST   /{id}/install  # 安装Plugin
│   └── DELETE /{id}          # 卸载
│
├── /sync/                    # 🆕 多端同步
│   ├── WS   /ws              # WebSocket连接
│   ├── GET  /events          # SSE事件流
│   └── POST /push-token      # 注册推送Token
│
├── /billing/                 # 🆕 商业化
│   ├── GET  /subscription    # 当前订阅
│   ├── POST /subscribe       # 订阅
│   ├── GET  /plans           # 套餐列表
│   └── GET  /invoices        # 账单
│
└── /admin/                   # 管理（现有，保留）
    ├── /providers
    ├── /model-routes
    ├── /budgets
    └── /prompts
```

### 10.3 统一响应信封

```json
// 成功
{
  "code": "SUCCESS",
  "message": "操作成功",
  "data": { ... }
}

// 错误
{
  "code": "PROVIDER_RATE_LIMITED",
  "message": "AI服务暂时繁忙，请稍后重试",
  "data": null,
  "trace_id": "abc-123"
}
```

### 10.4 流式响应（SSE）

```
GET /api/v1/engine/chat
Headers: Authorization: Bearer <token>

Response (SSE):
data: {"type": "delta", "content": "你好"}
data: {"type": "delta", "content": "，我"}
data: {"type": "delta", "content": "是星禾"}
data: {"type": "done", "usage": {"input_tokens": 100, "output_tokens": 50}}
```

---

## 十一、数据同步

### 11.1 同步架构

```
┌─────────┐     ┌─────────┐     ┌─────────┐
│ PC Web  │     │ Android │     │   iOS   │
└────┬────┘     └────┬────┘     └────┬────┘
     │                │                │
     │  SSE/WebSocket │                │
     ▼                ▼                ▼
┌──────────────────────────────────────────┐
│           Sync Service (FastAPI)          │
│  ┌──────────┐  ┌──────────┐  ┌────────┐  │
│  │WebSocket │  │   SSE    │  │  Push  │  │
│  │ Manager  │  │  Stream  │  │Service │  │
│  └──────────┘  └──────────┘  └────────┘  │
│                      │                     │
│            ┌─────────▼─────────┐          │
│            │   Event Bus       │          │
│            │   (Redis PubSub)  │          │
│            └───────────────────┘          │
└──────────────────────────────────────────┘
```

### 11.2 同步策略

| 场景 | 方案 | 说明 |
|------|------|------|
| **AI流式输出** | SSE | 单向服务端推送，轻量高效 |
| **实时状态同步** | WebSocket | 双向通信，Agent状态/协作 |
| **任务通知** | Push Notification | Agent完成/热点发现 |
| **数据变更** | 乐观更新 + 后台同步 | 移动端操作即时响应 |
| **离线队列** | 本地队列 + 上线同步 | 移动端弱网环境 |
| **冲突解决** | 版本号 + 三方对比 | 多端同时编辑 |

### 11.3 实时事件类型

| 事件 | 通道 | 说明 |
|------|------|------|
| `agent.run.started` | WS/Push | Agent开始执行 |
| `agent.run.progress` | WS | Agent执行进度 |
| `agent.run.completed` | WS/Push | Agent执行完成 |
| `agent.run.failed` | WS/Push | Agent执行失败 |
| `content.generated` | WS/Push | 内容生成完成 |
| `hotspot.discovered` | Push | 新热点发现 |
| `chapter.ready` | WS/Push | 章节生成完成 |
| `project.updated` | WS | 项目信息更新 |

### 11.4 离线策略

```
移动端离线层级：

L1 — 即时响应
  用户操作 → 乐观更新UI → 后台同步
  失败 → 回滚UI + 提示

L2 — 离线队列
  网络不可用 → 操作入队(SQLite) → 网络恢复 → 批量同步
  冲突 → 版本对比 → 用户选择

L3 — 预加载
  WiFi环境 → 预加载项目列表/最近章节
  移动网络 → 仅加载关键数据
```

---

## 十二、Skill体系

### 12.1 Skill定义

Skill是**可安装、可启用、可禁用、可升级、可卸载**的独立AI能力单元。

### 12.2 Skill模型

```json
{
  "id": "skill_novel_explosive_title",
  "name": "爆款标题生成",
  "version": "1.2.0",
  "category": "novel",
  "description": "基于市场趋势分析，生成高点击率的小说标题",
  "author": "星禾官方",
  "icon": "sparkles",
  "inputs": {
    "genre": { "type": "string", "required": true, "description": "小说类型" },
    "theme": { "type": "string", "required": false, "description": "核心主题" },
    "keywords": { "type": "array", "required": false, "description": "关键词" }
  },
  "output": {
    "type": "array",
    "items": {
      "title": "string",
      "score": "number",
      "reason": "string"
    }
  },
  "prompt_template": "skill_novel_explosive_title_v2",
  "model_preference": "deepseek-chat",
  "estimated_tokens": 500,
  "price": 0,
  "status": "active",
  "installed_at": "2026-07-20T10:00:00Z"
}
```

### 12.3 Skill分类体系

| 类别 | 示例Skills |
|------|-----------|
| **小说创作** | 爆款标题、黄金三章、人物设计、世界观构建、AI降味、章节大纲 |
| **内容运营** | 热点选题、SEO标题、多平台改写、摘要生成 |
| **知识管理** | 知识提取、自动标签、相似度检测、风格学习 |
| **效率工具** | 文本润色、语法检查、格式转换、批量处理 |
| **数据分析** | 市场趋势、竞品分析、读者画像 |

### 12.4 Skill生命周期

```
安装 (Install)
    ↓
启用 (Enable) ←→ 禁用 (Disable)
    ↓
升级 (Upgrade)
    ↓
卸载 (Uninstall)
```

### 12.5 Skill调用流程

```
用户触发 → Skill Manager验证权限
         → AI Engine加载Prompt模板
         → 装配上下文
         → Provider执行
         → 返回结构化结果
         → 记录使用统计
```

---

## 十三、Agent体系

### 13.1 Agent定义

Agent不是简单Prompt，而是包含**目标、Memory、Tools、Skills、Workflow**的自主AI实体。

### 13.2 Agent模型

```json
{
  "id": "agent_novel_author",
  "name": "小说作者Agent",
  "description": "全自动完成从市场分析到成书的全流程",
  "goal": "创作一部高质量的市场导向型小说",
  "model": "claude-sonnet-4-20250514",
  "tools": ["web_search", "ranking_scanner", "content_editor"],
  "skills": ["爆款标题", "黄金三章", "人物设计", "AI降味"],
  "workflow": {
    "steps": [
      { "id": "market_analysis", "skill": "market_analysis", "timeout": 300 },
      { "id": "topic_selection", "skill": "topic_selection", "depends_on": ["market_analysis"] },
      { "id": "outline_generation", "skill": "outline_generation", "depends_on": ["topic_selection"] },
      { "id": "character_design", "skill": "character_design", "depends_on": ["outline_generation"] },
      { "id": "chapter_generation", "skill": "chapter_generation", "depends_on": ["character_design"], "loop": true },
      { "id": "quality_check", "skill": "quality_check", "depends_on": ["chapter_generation"] }
    ]
  },
  "memory": {
    "type": "conversation_buffer",
    "max_tokens": 8000
  },
  "schedule": "manual",
  "status": "idle"
}
```

### 13.3 预置Agent

| Agent | 功能 | 触发方式 |
|-------|------|----------|
| **小说作者Agent** | 扫榜→选题→大纲→人物→章节→审核 全流程 | 手动/定时 |
| **热点分析Agent** | 定时扫描热点平台，生成每日晨报 | 定时（每6小时） |
| **内容审核Agent** | 自动检查AI味道/一致性/质量 | 内容生成后自动 |
| **发布助手Agent** | 多平台内容适配+发布排期 | 手动触发 |
| **知识管家Agent** | 自动整理知识库，提取标签和关联 | 定时/手动 |

### 13.4 Agent运行状态机

```
idle → pending → running → completed
                  ↓
              waiting_human → running → completed
                  ↓
              failed → retry → running → completed
```

---

## 十四、Plugin体系

### 14.1 Plugin定义

Plugin是**扩展平台能力的第三方模块**，可提供新的数据源、发布渠道、内容格式等。

### 14.2 Plugin类型

| 类型 | 说明 | 示例 |
|------|------|------|
| **数据源Plugin** | 新增扫榜/热点数据源 | 豆瓣、知乎、微博 |
| **发布渠道Plugin** | 新增发布平台 | 新小说平台、社交媒体 |
| **格式Plugin** | 新增内容格式支持 | EPUB导出、PDF排版 |
| **AI Provider Plugin** | 新增AI模型供应商 | 本地模型、新云端模型 |
| **UI主题Plugin** | 自定义界面主题 | 品牌定制主题 |
| **工具Plugin** | 通用工具集成 | 字数统计、查重、翻译 |

### 14.3 Plugin模型

```json
{
  "id": "plugin_douban_source",
  "name": "豆瓣数据源",
  "version": "1.0.0",
  "type": "datasource",
  "author": "社区开发者",
  "description": "接入豆瓣读书评分和评论数据",
  "permissions": ["network", "storage"],
  "config_schema": {
    "api_key": { "type": "string", "required": false }
  },
  "status": "active"
}
```

### 14.4 Plugin Marketplace

```
Plugin Marketplace
├── 浏览/搜索Plugin
├── 一键安装
├── 版本管理
├── 权限控制
├── 评分/评论
└── 开发者中心（上传/管理/收益）
```

---

## 十五、SaaS商业化

### 15.1 套餐体系

| 特性 | 免费版 | Pro版 | 团队版 | 企业版 |
|------|--------|-------|--------|--------|
| **月价格** | ¥0 | ¥99/月 | ¥299/月 | 定制 |
| **AI额度** | 10万token/月 | 100万token/月 | 500万token/月 | 不限 |
| **模型** | DeepSeek基础 | 全部模型 | 全部模型 | 全部+私有部署 |
| **项目数** | 3个 | 不限 | 不限 | 不限 |
| **Skills** | 官方免费Skills | 全部Skills | 全部Skills | 全部+定制 |
| **Agent** | 1个 | 5个 | 20个 | 不限 |
| **协作** | 个人 | 个人 | 5人 | 不限 |
| **知识库** | 100条 | 1000条 | 1万条 | 不限 |
| **发布渠道** | 3个 | 全部 | 全部 | 全部 |
| **API访问** | ❌ | ❌ | ✅ | ✅ |
| **优先支持** | ❌ | ✅ | ✅ | ✅ |
| **SSO** | ❌ | ❌ | ❌ | ✅ |

### 15.2 移动端商业化

| 特性 | 说明 |
|------|------|
| **应用内购买** | Google Play / App Store 订阅 |
| **会员同步** | 同一账户跨端共享会员 |
| **额度显示** | 移动端实时显示剩余Token额度 |
| **免费试用** | 7天Pro免费试用 |
| **家庭共享** | 未来支持（Apple Family Sharing） |

### 15.3 计费系统设计

```
计费维度：
├── 订阅费用（按月/年）
├── AI Token消耗（超额度按量付费）
├── Skill市场（付费Skill分成）
├── Plugin市场（付费Plugin分成）
└── 企业定制（独立报价）

计费流程：
用户使用AI → Token Tracker记录 → 预算校验 → 超限拦截/提示升级
```

---

## 十六、开发路线

### 16.1 总体时间线

```
2026 Q3          2026 Q4          2027 Q1          2027 Q2          2027 Q3+
    │                │                │                │                │
Phase 0          Phase 1          Phase 2          Phase 3          Phase 4-5
平台基础         Web升级          移动Web          Android App      iOS + 生态
```

### 16.2 Phase 0：平台基础（2026 Q3，4-6周）

**目标**：在不破坏现有功能的前提下，建立平台基础架构。

| 任务 | 内容 | 预估 |
|------|------|------|
| **P0-1** | AI Engine统一封装（统一Provider调用入口） | 1周 |
| **P0-2** | 模块化目录重构（按modules/组织业务代码） | 1周 |
| **P0-3** | Skill Manager核心（安装/启用/禁用/卸载） | 1周 |
| **P0-4** | Agent Manager核心（Agent定义/运行/状态） | 1周 |
| **P0-5** | 统一错误信封 + 鉴权收敛（已完成部分） | 0.5周 |
| **P0-6** | OpenAPI 3.1契约生成 + 验证 | 0.5周 |
| **P0-7** | 多端Design Token定义（Web + Mobile） | 0.5周 |
| **P0-8** | 回归测试（493+测试保持通过） | 持续 |

**门禁**：所有现有测试通过 + 新API契约验证通过 + 前端构建成功

### 16.3 Phase 1：Web升级（2026 Q3-Q4，6-8周）

**目标**：完成PC Web工作台UI升级，实现模块化应用架构。

| 任务 | 内容 | 预估 |
|------|------|------|
| **P1-1** | 设计系统全组件对齐Token（B8收尾） | 1周 |
| **P1-2** | 工作台首页重构（DashboardV2真实数据驱动） | 1周 |
| **P1-3** | 三栏布局完善（可折叠/拖拽/响应式） | 1周 |
| **P1-4** | 小说模块独立化（NovelApp内聚） | 1周 |
| **P1-5** | 命令面板增强（全局AI命令） | 0.5周 |
| **P1-6** | Skill/Agent管理界面 | 1周 |
| **P1-7** | 多窗口/多Tab支持 | 1周 |
| **P1-8** | 响应式完善（三栏→双栏→单栏） | 0.5周 |
| **P1-9** | 性能优化 + 打包优化 | 0.5周 |

**门禁**：全量E2E测试通过 + 明暗双模式截图验收 + 对标产品并排自评

### 16.4 Phase 2：移动Web（2026 Q4-2027 Q1，4-6周）

**目标**：移动Web适配 + PWA增强。

| 任务 | 内容 | 预估 |
|------|------|------|
| **P2-1** | 移动端响应式布局（单栏设计） | 1.5周 |
| **P2-2** | 移动端导航（底部Tab Bar） | 1周 |
| **P2-3** | 核心页面移动适配（首页/AI助手/项目/任务/我的） | 1.5周 |
| **P2-4** | PWA增强（离线缓存L2 + 推送通知） | 1周 |
| **P2-5** | 移动端性能优化 + 触控体验 | 0.5周 |

**门禁**：Lighthouse Mobile Score ≥ 85 + PWA可安装 + 离线可用

### 16.5 Phase 3：Android App（2027 Q1-Q2，8-10周）

**目标**：发布Android原生应用，核心移动AI创作体验。

| 任务 | 内容 | 预估 |
|------|------|------|
| **P3-1** | React Native + Expo项目初始化 + 共享包搭建 | 1周 |
| **P3-2** | 设计系统落地（Android原生组件+Token） | 1周 |
| **P3-3** | 认证模块（登录/注册/生物识别） | 1周 |
| **P3-4** | 首页 + 底部导航框架 | 1周 |
| **P3-5** | AI助手页面（SSE流式对话 + 文件上传） | 2周 |
| **P3-6** | 项目页面（项目列表/详情/创建） | 1周 |
| **P3-7** | 任务页面（Agent状态/通知/生成记录） | 1周 |
| **P3-8** | 设置页面（模型/账户/会员） | 0.5周 |
| **P3-9** | 推送通知（FCM + 国产厂商） | 1周 |
| **P3-10** | 离线模式 + 语音输入 | 1周 |
| **P3-11** | Google Play上架 | 0.5周 |

**门禁**：Google Play审核通过 + 核心场景E2E测试 + Crash率<0.5%

### 16.6 Phase 4：iOS App（2027 Q2，4-6周）

**目标**：复用Android代码库，发布iOS版本。

| 任务 | 内容 | 预估 |
|------|------|------|
| **P4-1** | iOS原生模块适配（APNs/FaceID/Widget） | 1.5周 |
| **P4-2** | iOS设计规范适配（HIG） | 1周 |
| **P4-3** | iOS特定功能（Siri Shortcuts/Handoff） | 1周 |
| **P4-4** | TestFlight测试 | 0.5周 |
| **P4-5** | App Store上架 | 0.5周 |

**门禁**：App Store审核通过 + iOS设计规范合规

### 16.7 Phase 5：生态系统（2027 Q3+，持续）

| 任务 | 内容 |
|------|------|
| **P5-1** | Plugin Marketplace上线 |
| **P5-2** | Skill社区（开发者上传/审核/分成） |
| **P5-3** | Agent模板市场 |
| **P5-4** | 团队协作增强 |
| **P5-5** | 企业版私有部署方案 |
| **P5-6** | 国际化（英语/日语等） |

---

## 十七、风险分析

### 17.1 技术风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| **React Native性能不足** | 低 | 中 | Phase 3前做性能原型验证；复杂动画降级为原生模块 |
| **多端同步数据冲突** | 中 | 高 | 版本号+三方对比+乐观锁；严格测试冲突场景 |
| **AI Engine重构影响现有功能** | 中 | 高 | 渐进式封装，不改变现有Provider调用路径 |
| **移动端SSE连接稳定性** | 中 | 中 | 自动重连+Last-Event-ID断点续传；弱网降级为轮询 |
| **数据库迁移兼容性** | 低 | 高 | 严格Alembic单头线性迁移；全量回归测试 |
| **第三方依赖风险** | 低 | 中 | 优先使用成熟库；关键依赖锁定版本；定期安全审计 |

### 17.2 产品风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| **移动端功能定位模糊** | 中 | 中 | 明确移动端"查看+轻量操作"定位，不做PC功能搬运 |
| **Skill/Agent生态冷启动** | 高 | 中 | 官方预置20+高质量Skills和5个Agent；提供开发者文档 |
| **商业化转化率低** | 中 | 高 | 免费版提供真实价值；Pro版差异化AI额度+高级Skills |
| **用户学习成本高** | 中 | 中 | 交互引导+模板+预置工作流；移动端保持简洁 |

### 17.3 组织风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| **多端并行开发资源不足** | 高 | 高 | 严格按Phase顺序执行；Phase 3前验证移动端方案 |
| **技术栈分裂** | 低 | 中 | 坚持RN方案，避免引入Dart/Swift分散技术栈 |
| **维护成本上升** | 中 | 中 | 共享包最大化代码复用；自动化测试覆盖 |

### 17.4 风险应对总策略

```
高风险 → Phase内必须验证原型
中风险 → Phase前准备缓解方案
低风险 → 持续监控，不阻塞开发
```

---

## 附录A：关键决策记录

| 决策 | 结论 | 日期 |
|------|------|------|
| **移动端框架** | React Native + Expo SDK 52 | 2026-07-20 |
| **状态管理** | 保持React Context + Hooks（不引入zustand） | 2026-07-20 |
| **路由方案** | Web保持internal state，移动端React Navigation | 2026-07-20 |
| **CSS方案** | 保持CSS Custom Properties + Design Token | 2026-07-20 |
| **API契约** | OpenAPI 3.1作为唯一事实源 | 2026-07-20 |
| **数据库** | 保持PostgreSQL + pgvector，不做变更 | 2026-07-20 |
| **消息队列** | 保持Celery + Redis，不做变更 | 2026-07-20 |
| **微服务** | 不做拆分，保持模块化单体 | 2026-07-20 |

## 附录B：现有项目资产保留清单

| 资产 | 保留 | 说明 |
|------|------|------|
| 全部后端代码(backend/app/) | ✅ | 渐进重构，不推倒 |
| 全部数据库迁移(alembic/) | ✅ | 保持单头线性 |
| 全部测试(tests/) | ✅ | 回归门禁 |
| 前端核心组件(29个) | ✅ | 渐进升级 |
| 设计系统(doc12 tokens) | ✅ | 扩展多端Token |
| API端点(129条) | ✅ | 保持兼容，新增 |
| AI Provider集成 | ✅ | 统一到AI Engine |
| 安全机制(JWT/BYOK) | ✅ | 增强移动端 |
| Docker部署方案 | ✅ | 扩展移动端CI |
| 开发文档(19篇) | ✅ | 补充多端文档 |

---

> **文档版本**：V1.0 | **编制日期**：2026-07-20
>
> **编制角色**：CPO · CTO · AI Agent架构师 · SaaS产品经理 · Web架构师 · Android架构师 · iOS架构师 · UI/UX设计总监
>
> **下一步**：进入 Phase 0 详细任务拆解与执行
