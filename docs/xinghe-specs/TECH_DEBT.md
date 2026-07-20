# 星禾AI工作台 · 技术债

> 版本：V1.0 | 日期：2026-07-20
>
> ⚠️ 禁止无限堆技术债。每次迭代必须清理部分技术债。

---

## 技术债登记

### 格式

```
TD-xxx | 优先级 | 影响范围 | 预计时间 | 状态

**问题**：描述
**影响**：对产品/开发的影响
**解决方案**：建议方案
**关联**：相关模块/文件
```

---

## 当前技术债清单

### TD-001 | P2 | Web前端 | 1周 | 🔲

**问题**：部分组件仍使用旧版CSS类名，未完全对齐Design Token（doc12 compat.css过渡期）

**影响**：视觉不一致，维护双套样式

**解决方案**：逐组件迁移到Token变量，移除compat.css别名层

**关联**：frontend/src/components/*

---

### TD-002 | P2 | Web前端 | 0.5周 | 🔲

**问题**：DashboardV2仍有部分mock数据占位，工作台首页数据不全

**影响**：工作台首页不是真实数据驱动

**解决方案**：接入真实API（projects列表、最近小说、Agent状态）

**关联**：DashboardV2.tsx, Overview.tsx

---

### TD-003 | P3 | Web前端 | 1周 | 🔲

**问题**：三屏（Dashboard/Overview/Workspace）关系不清晰，Overview.tsx硬编码，workspace tab是stub

**影响**：用户困惑导航结构

**解决方案**：合并为工作台+数据概览，移除冗余workspace tab

**关联**：App.tsx, DashboardV2.tsx, Overview.tsx

---

### TD-004 | P2 | 后端 | 0.5周 | 🔲

**问题**：`ok()` 函数历史上多处重复定义，虽然authz.py已收敛为唯一来源，但旧项目中可能仍有残留

**影响**：返回格式不一致风险

**解决方案**：全仓搜索确认仅authz.py一处定义

**关联**：authz.py, main.py, api/v1/*

---

### TD-005 | P3 | 后端 | 1周 | 🔲

**问题**：config.py中存在标记deprecated的配置项（bootstrap_budget_cny等）

**影响**：配置混乱，新人困惑

**解决方案**：确认无引用后物理删除或迁移到数据库

**关联**：config.py

---

### TD-006 | P1 | 后端 | 1周 | 🔲

**问题**：AI调用分散在多处（gateway.py + 各service直接调provider），未统一到AI Engine

**影响**：Token统计不统一，成本追踪可能遗漏

**解决方案**：建立engine/统一入口，逐步迁移调用点

**关联**：gateway.py, services/*, api/v1/*

---

### TD-007 | P3 | 基础设施 | 0.5周 | 🔲

**问题**：缺少Prometheus/Grafana监控

**影响**：生产问题发现滞后

**解决方案**：Phase 2加入监控栈

**关联**：docker-compose.yml

---

### TD-008 | P2 | Web前端 | 0.5周 | 🔲

**问题**：移动端响应式不完善，部分页面在手机端布局错乱

**影响**：移动Web体验差

**解决方案**：按UI_UX_GUIDE.md规范做响应式适配

**关联**：frontend/src/components/*, frontend/src/design/

---

## 技术债统计

| 优先级 | 数量 | 总预估时间 |
|--------|------|-----------|
| P1-紧急 | 1 | 1周 |
| P2-高 | 4 | 2.5周 |
| P3-中 | 4 | 3周 |
| **合计** | **9** | **6.5周** |

---

## 清理计划

每Phase必须清理对应优先级的技术债：

- **Phase 1**：清理所有P1 + 至少50% P2
- **Phase 2**：清理剩余P2 + 至少50% P3
- **Phase 3**：清理所有P3
