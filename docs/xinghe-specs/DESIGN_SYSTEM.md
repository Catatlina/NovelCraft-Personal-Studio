# 星禾AI工作台 · 设计系统规范

> 版本：V1.0 | 日期：2026-07-20 | 角色：UI/UX设计负责人
>
> 基于 NovelCraft doc12 设计系统，扩展为星禾AI工作台统一设计规范。

---

## 一、设计价值观

| 原则 | 说明 |
|------|------|
| **Calm by default** | 默认安静，低饱和中性底，高亮只给"此刻重要的事" |
| **Dense but breathe** | 高密度 + 规律留白，不拥挤 |
| **Keyboard is first-class** | Web端每个动作有快捷键，⌘K可达 |
| **Dark-native** | 暗色为原生默认，亮色是变体而非补丁 |
| **Motion with restraint** | 动效克制，默认 ≤200ms |
| **Content-first** | 内容优先，UI是背景不是主角 |

---

## 二、对标基准

| 维度 | 对标 | 学什么 |
|------|------|--------|
| 信息密度 | Linear | 紧凑列表/表格、状态用色点、键盘优先 |
| 编辑沉浸 | Notion / Cursor | 块编辑流畅、选中即出AI浮条 |
| 命令交互 | Raycast | ⌘K全局命令、模糊搜索、动作即命令 |
| 视觉质感 | Apple | 简洁高级、细腻动效 |

---

## 三、Design Tokens

### 3.1 品牌色（Brand / Accent）

品牌主色：低饱和靛蓝 Indigo

| Token | Dark HEX | Light HEX | 用途 |
|-------|----------|-----------|------|
| `--brand-50` | #EEF0FE | #F1F3FE | 极浅底 |
| `--brand-100` | #D9DEF9 | #DCE2FB | 浅底/hover |
| `--brand-300` | #838DEB | #7884E0 | 弱强调 |
| `--brand-500` | **#5B66DB** | **#4F5BD6** | **主色/主按钮** |
| `--brand-600` | #444FCB | #3E48C2 | 主色按压 |
| `--brand-700` | #373FA8 | #313A9E | 深强调 |
| `--brand-foreground` | #FFFFFF | #FFFFFF | 主色上文字 |

### 3.2 中性色（Neutral）

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

### 3.3 语义色（Semantic）

| Token | Dark HEX | Light HEX | 用途 |
|-------|----------|-----------|------|
| `--success` | #31B572 | #2C9C62 | 通过/成功 |
| `--success-bg` | #163A28 | #E1F5EA | 成功底 |
| `--warning` | #F2A93B | #D98E1F | 风险/警告 |
| `--warning-bg` | #3D2E12 | #FBEEDB | 警告底 |
| `--danger` | #DE4B5E | #CC3B4E | 错误/拦截 |
| `--danger-bg` | #3F1820 | #FBE3E7 | 错误底 |
| `--info` | #2E9BD6 | #1878B8 | 信息/提示 |
| `--info-bg` | #143545 | #E0EFFA | 信息底 |

### 3.4 字体阶（Type Scale）

基于 1.2 缩放比，根字号 14px

| Token | 字号/行高 | 用途 |
|-------|-----------|------|
| `--text-xs` | 11px / 16px | 标签/脚注 |
| `--text-sm` | 12px / 18px | 次要信息/表格单元 |
| `--text-base` | 14px / 21px | 正文/默认 |
| `--text-md` | 16px / 24px | 小标题/卡片标题 |
| `--text-lg` | 19px / 28px | 区块标题 |
| `--text-xl` | 23px / 32px | 页标题 |
| `--text-2xl` | 28px / 36px | 大标题（少用） |
| `--editor-text` | 16px / 1.8 | 编辑器正文 |

### 3.5 间距阶（4px基）

| Token | 值 | 用途 |
|-------|-----|------|
| `--space-1` | 4px | icon与文字间隙 |
| `--space-2` | 8px | 紧凑组内 |
| `--space-3` | 12px | 控件内边距 |
| `--space-4` | 16px | 卡片内边距/区块间隙 |
| `--space-5` | 20px | 列表项间隙 |
| `--space-6` | 24px | 面板内边距 |
| `--space-8` | 32px | 区块间距 |
| `--space-10` | 40px | 大区块 |
| `--space-12` | 48px | 页级留白 |

### 3.6 圆角（Radius）

| Token | 值 | 用途 |
|-------|-----|------|
| `--radius-sm` | 4px | 标签/小控件 |
| `--radius-md` | 6px | 按钮/输入/卡片 |
| `--radius-lg` | 10px | 浮层/弹窗 |
| `--radius-xl` | 14px | 大弹窗/面板 |
| `--radius-full` | 9999px | 头像/胶囊 |

### 3.7 阴影（Shadow）

| Token | Dark | Light | 用途 |
|-------|------|-------|------|
| `--shadow-sm` | 0 1px 2px rgba(0,0,0,.4) | 0 1px 3px rgba(0,0,0,.08) | 卡片 |
| `--shadow-md` | 0 4px 12px rgba(0,0,0,.45) | 0 4px 12px rgba(0,0,0,.10) | 浮条/下拉 |
| `--shadow-lg` | 0 12px 32px rgba(0,0,0,.55) | 0 12px 32px rgba(0,0,0,.14) | 弹窗/命令面板 |
| `--shadow-focus` | 0 0 0 2px var(--brand-500) | 0 0 0 2px var(--brand-500) | 焦点环 |

### 3.8 动效（Motion）

| Token | 值 | 用途 |
|-------|-----|------|
| `--dur-fast` | 120ms | hover/微交互 |
| `--dur-base` | 180ms | 展开/收起/浮条 |
| `--dur-slow` | 260ms | 弹窗/面板入场 |
| `--ease-standard` | cubic-bezier(0.2, 0, 0, 1) | 默认缓动 |

---

## 四、组件规范

### 4.1 组件清单

| 组件 | 变体 | 说明 |
|------|------|------|
| **Button** | primary / secondary / ghost / danger / subtle | sm(28px) / md(32px) / lg(36px) |
| **Input** | default / error / success | 含label/helper/error text |
| **Select** | default / compact | 表格内用compact |
| **Dialog** | — | 圆角xl + 阴影lg + 遮罩 |
| **Toast** | success / warning / danger / info | 语义色左边条 |
| **Tabs** | 下划线式 | active主色下划 |
| **DataTable** | 紧凑行高32px | 列宽拖拽、虚拟滚动(>500行) |
| **EmptyState** | — | 图标+标题+说明+操作按钮 |
| **Skeleton** | — | 加载占位 |
| **Badge** | — | 状态标签 |
| **Avatar** | — | 用户头像 |
| **Tooltip** | — | 延迟200ms出现 |
| **CommandPalette** | — | ⌘K唤起，模糊搜索 |
| **Progress** | linear / radial | 进度条/环形进度 |

### 4.2 组件开发规则

1. **只用Token**：禁止硬编码颜色、字号、间距。所有视觉属性使用 `var(--token-name)`
2. **四态齐全**：每个组件必须覆盖 loading / empty / error / success
3. **键盘可达**：焦点环 + Tab可达
4. **暗亮双模式**：两套截图验证

---

## 五、布局规范

### 5.1 三栏工作台（Web）

```
┌──────────┬──────────────────────────────┬──────────────┐
│ 导航侧栏  │        主工作区               │   AI面板     │
│ 220px    │   自适应填充                  │   320px      │
│ 可折叠   │                              │   可折叠     │
└──────────┴──────────────────────────────┴──────────────┘
              顶栏 48px: 面包屑 · ⌘K · 主题 · 头像
```

### 5.2 响应式断点

| 断点 | 宽度 | 布局 |
|------|------|------|
| `sm` | ≥640px | 单栏（移动优先） |
| `md` | ≥768px | 双栏（左栏+主区） |
| `lg` | ≥1024px | 三栏（加AI面板） |
| `xl` | ≥1280px | 三栏+主区最大宽1200px居中 |

---

## 六、主题切换

```
实现方式：
<html data-theme="dark|light">

初始化逻辑：
localStorage.nc-theme → matchMedia('prefers-color-scheme') → 默认dark

切换行为：
只改 data-theme 属性 + 写localStorage
不闪白（index.html内联脚本预判）
```

---

## 七、禁止事项

| ❌ 禁止 | ✅ 正确做法 |
|--------|-----------|
| 页面内随意写CSS | 使用Design Token + 组件 |
| 硬编码颜色 `#14161C` | 使用 `var(--bg-base)` |
| 硬编码字号 `14px` | 使用 `var(--text-base)` |
| 重复开发按钮 | 使用 `<Button variant="primary">` |
| 自己写弹窗 | 使用 `<Dialog>` |
| 传统后台管理风格 | Apple/Linear/Notion风格 |
| 大量卡片堆叠 | 信息分层，渐进展示 |
| 大量表格 | 列表/卡片替代，表格仅用于数据密集场景 |

---

> **下一步**：阅读 [UI_UX_GUIDE.md](./UI_UX_GUIDE.md) 了解信息架构和交互规范
