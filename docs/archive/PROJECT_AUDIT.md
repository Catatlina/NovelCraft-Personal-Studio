# 星禾AI工作台 · 项目审计报告

> 日期：2026-07-20 | 基于：NovelCraft V2.2 | 角色：CTO · 架构师

## 一、总体评估

| 维度 | 状态 | 评分 |
|------|------|------|
| 后端稳定性 | 492+测试通过，生产级 | ⭐⭐⭐⭐⭐ |
| AI能力 | 4 Provider，完整gateway | ⭐⭐⭐⭐⭐ |
| 前端功能 | 19页面，全后端接线 | ⭐⭐⭐⭐ |
| 设计系统 | Token系统存在但未完全对齐 | ⭐⭐⭐ |
| 模块化 | 后端扁平结构，前端单体 | ⭐⭐ |
| 可扩展性 | 架构可支持但需渐进改造 | ⭐⭐⭐ |

## 二、前端设计系统审计

### 亮点
- 39个组件均使用CSS变量，**组件TSX文件零硬编码颜色**
- doc12 token系统完整（colors/spacing/typography/shadow/motion/z-index）
- ThemeProvider + data-theme双模式切换已实现
- compat.css别名层存在，迁移路径清晰

### 需修复（快速）

| 文件 | 问题 | 硬编码数 |
|------|------|----------|
| `global-v2.css` | 硬编码hex `#e0e0e0` `#fff` `#ccc` `#de4b5e` `#5b9cf5` `#8b8fa8` | 13 hex + 25 rgba |
| `styles.css` | 节点状态硬编码 `#1a3a28` `#1a2a4a` `#3a251a` `#3a1520` | 9 hex + 1 rgba |
| `components.css` | 图标/徽章rgba硬编码 | 15 rgba |
| `novelcraft-theme.css` | `--nc-*`独立token系统 | 需合并到doc12 |

### 需修复（渐进）

| 项 | 影响范围 | 优先级 |
|-----|---------|--------|
| 组件内联px值→`var(--space-*)` | ~300+处 | P3 |
| 组件内联fontSize→`var(--text-*)` | ~100+处 | P3 |

## 三、后端架构审计

### 当前状态
- 92个Python文件，83个测试文件，16个API路由模块
- 结构：扁平化，`api/v1/` + `services/` + `workers/`
- 缺少 `apps/` `engine/` `platform/` 分层
- AI调用通过 `gateway.py` 和 `ai/providers.py`，但各模块也可直接import

### Phase 1目标
- [ ] 建立 `engine/` 目录，统一AI调用入口
- [ ] 所有AI调用经过 `engine/router.py`
- [ ] `apps/novel/` 渐进迁移小说业务逻辑

## 四、Phase 1 执行计划

### 本轮：CSS Token化（P0）
1. `global-v2.css` → 全部替换为 doc12 token
2. `styles.css` → 节点状态色提取为token
3. `components.css` → rgba替换
4. 验证暗/亮双模式

### 下轮：AI Engine（P0）
1. 建立 `engine/__init__.py` `engine/router.py`
2. 统一Token统计
3. 渐进迁移调用点

### 后续：Dashboard + Skill基础（P1）
1. 工作台首页真实数据
2. Skill Manager基础

## 五、风险

| 风险 | 缓解 |
|------|------|
| CSS修改导致视觉断裂 | 逐文件替换，截图对比 |
| 组件依赖nc-theme变量 | compat.css别名层保护 |
| AI Engine影响现有调用 | 渐进封装，不改变调用路径 |
