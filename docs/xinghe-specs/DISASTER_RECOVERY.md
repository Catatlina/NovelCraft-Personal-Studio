# 星禾AI工作台 · 灾难恢复方案

> 版本：V1.0 | 日期：2026-07-17

## 一、风险矩阵

| 灾难场景 | 影响 | RPO | RTO |
|---|---|---|---|
| 新加坡VPS宕机 | NovelCraft不可用 | 24h (日备) | <30min |
| 日本VPS宕机 | VPN/代理全部中断 | 即时 | <5min (切美国) |
| 数据库损坏 | 全部数据丢失 | 24h | <1h |
| 代码误删 | 功能回退 | 0 (Git) | <10min |
| Ubuntu硬盘故障 | 备份丢失 | 24h | 重建 |

## 二、恢复步骤

### 新加坡宕机
```bash
# 1. 云控制台重启VPS
# 2. VPS启动后自动拉起Docker (restart=always)
# 3. 验证: curl https://novel.xyjin.xyz/api/v1/healthz
# 4. 若Docker未启动: cd /opt/NovelCraft-Personal-Studio && docker compose up -d
```

### 日本宕机（VPN中断）
```bash
# VPN客户端自动切换到美国备用节点 (url-test fallback)
# 扫榜代理链中断 → 起点/番茄不可采，纵横仍可用
# 恢复日本后自动切回
```

### 数据库恢复
```bash
# 从Ubuntu恢复最新备份
scp root@192.168.31.22:/backups/sg/novelcraft-$(date +%Y%m%d)-*.sql.gz .
gunzip novelcraft-*.sql.gz
psql -U novelcraft -d novelcraft < novelcraft-*.sql
docker compose restart api worker
```

### 代码回滚
```bash
git log --oneline -5           # 找到上一个好的commit
git reset --hard <good-commit>
nc-deploy                       # 一键部署
```

## 三、备份清单

| 数据 | 位置 | 频率 | 保留 |
|---|---|---|---|
| PostgreSQL | Ubuntu:/backups/sg/ | 每日 03:00 | 7天 |
| 日本配置 | Ubuntu:/backups/jp/ | 每日 04:00 | 7天 |
| 美国配置 | Ubuntu:/backups/us/ | 每日 04:00 | 7天 |
| 代码 | GitHub | 每次提交 | 永久 |

## 四、演练计划

| 项目 | 频率 | 方法 |
|---|---|---|
| DB恢复演练 | 每月 | 从备份恢复到临时库，验证表数量和数据完整性 |
| 配置恢复 | 每季 | 从备份还原日本xray配置到测试端口 |
| 全链路切换 | 每季 | 手动停日本VPN，验证美国自动接管 |
