# 星禾AI工作台 · 组件规范

> 版本：V1.0 | 日期：2026-07-20 | 角色：UI/UX设计负责人 · 前端负责人

---

## 一、组件化原则

| 原则 | 说明 |
|------|------|
| **出现2次必须组件化** | 同类UI模式出现2次，抽离为通用组件 |
| **优先成熟组件库** | Radix/shadcn 为基础，禁止重复造轮子 |
| **页面只负责组合** | 页面不写业务逻辑，只组合组件 |
| **Token驱动** | 所有视觉属性从Design Token获取 |

---

## 二、组件层级

```
components/
├── ui/                    # 基础UI组件（Radix/shadcn封装）
│   ├── Button.tsx
│   ├── Input.tsx
│   ├── Select.tsx
│   ├── Dialog.tsx
│   ├── Toast.tsx
│   ├── Tabs.tsx
│   ├── Badge.tsx
│   ├── Avatar.tsx
│   ├── Skeleton.tsx
│   ├── Tooltip.tsx
│   ├── Progress.tsx
│   ├── Switch.tsx
│   ├── Checkbox.tsx
│   ├── Slider.tsx
│   ├── Popover.tsx
│   └── DropdownMenu.tsx
│
├── common/                # 通用业务组件
│   ├── EmptyState.tsx     # 空状态
│   ├── DataTable.tsx      # 数据表格
│   ├── PageHeader.tsx     # 页面标题
│   ├── ConfirmDialog.tsx  # 确认弹窗
│   ├── ErrorBoundary.tsx  # 错误边界
│   └── CommandPalette.tsx # 命令面板
│
├── ai/                    # AI专用组件
│   ├── AIChat.tsx         # AI对话
│   ├── ChatBubble.tsx     # 聊天气泡
│   ├── StreamingText.tsx  # 流式文本
│   ├── AIFloatingBar.tsx  # AI浮条
│   └── SkillQuickAction.tsx # Skill快捷操作
│
├── novel/                 # 小说业务组件
│   ├── NovelCard.tsx      # 小说卡片
│   ├── ChapterList.tsx    # 章节列表
│   ├── CharacterCard.tsx  # 人物卡片
│   ├── ProgressTracker.tsx # 进度追踪
│   ├── ReviewRadar.tsx    # 审核雷达图
│   ├── DiffView.tsx       # Diff对比视图
│   └── VersionTree.tsx    # 版本树
│
├── content/               # 内容业务组件
│   ├── HotspotCard.tsx    # 热点卡片
│   ├── KnowledgeItem.tsx  # 知识条目
│   ├── PublishRecord.tsx  # 发布记录
│   └── CostChart.tsx      # 成本图表
│
└── layout/                # 布局组件
    ├── AppShell.tsx       # 三栏布局
    ├── Sidebar.tsx        # 侧栏导航
    ├── TopBar.tsx         # 顶栏
    ├── AIPanel.tsx        # AI侧面板
    └── MobileTabBar.tsx   # 移动端底部导航（Phase 2+）
```

---

## 三、组件开发规范

### 3.1 组件模板

```tsx
// Button.tsx
import { forwardRef } from 'react';
import type { ButtonProps } from './types';
import './Button.css'; // 仅使用Token变量

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', loading, children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn('nc-button', `nc-button--${variant}`, `nc-button--${size}`)}
        disabled={loading}
        {...props}
      >
        {loading && <Spinner />}
        {children}
      </button>
    );
  }
);
Button.displayName = 'Button';
```

### 3.2 必须覆盖的状态

每个组件必须有：

| 状态 | 说明 |
|------|------|
| **default** | 默认状态 |
| **hover** | 悬浮状态 |
| **active/pressed** | 按压状态 |
| **disabled** | 禁用状态 |
| **loading** | 加载状态 |
| **error** | 错误状态（如适用） |

### 3.3 Props规范

```tsx
interface ComponentProps {
  // 必须：variant, size, className
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  className?: string;

  // 必须：children 或 content
  children?: React.ReactNode;

  // 可选：disabled, loading
  disabled?: boolean;
  loading?: boolean;

  // 事件：通过 ...props 透传原生事件
}

// 使用 forwardRef 支持 ref 透传
```

---

## 四、变体规范

### Button

| 变体 | 用途 | 样式 |
|------|------|------|
| `primary` | 主要操作 | `bg-brand-500 text-white` |
| `secondary` | 次要操作 | `bg-bg-muted text-text-primary` |
| `ghost` | 弱操作 | `transparent text-text-secondary` |
| `danger` | 危险操作 | `bg-danger text-white` |
| `subtle` | 极弱操作 | `text-brand-500` |

### Input

| 变体 | 用途 |
|------|------|
| `default` | 默认 |
| `error` | 错误（危险红边） |
| `success` | 成功（绿色边） |

### Toast

| 变体 | 用途 | 左边条颜色 |
|------|------|-----------|
| `success` | 成功 | `var(--success)` |
| `warning` | 警告 | `var(--warning)` |
| `danger` | 错误 | `var(--danger)` |
| `info` | 信息 | `var(--info)` |

---

## 五、组件导出规范

每个组件目录：

```
Button/
├── Button.tsx          # 组件实现
├── Button.css          # 样式（Token变量）
├── Button.test.tsx     # 测试
├── Button.stories.tsx  # Storybook（可选）
├── index.ts            # 导出
└── types.ts            # 类型定义
```

统一从 `components/ui/` 或 `components/common/` 导出，禁止深层相对路径引用。

---

## 六、禁止事项

| ❌ 禁止 | ✅ 正确做法 |
|--------|-----------|
| 重复开发已存在的组件 | 查看组件清单，复用 |
| 页面内写 `<button style={{color:'#xxx'}}>` | 使用 `<Button variant="primary">` |
| 硬编码CSS颜色 | 使用 `var(--token-name)` |
| 自造Dialog/Modal | 使用封装好的 `<Dialog>` |
| 跳过组件四态 | loading/empty/error/success 齐全 |
| 不写displayName | 所有forwardRef组件必须设置 |
