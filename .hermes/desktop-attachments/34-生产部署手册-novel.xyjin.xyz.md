# NovelCraft 生产部署手册（novel.xyjin.xyz / 新加坡直连）

> 本文档是当前**唯一**权威部署指引，取代 33 号占位版。所有域名/IP/值均为真实值，可直接照做。
> 定案依据：4 机实测网络与硬件数据（见对话）。Sentry 本轮不启用。

## 0. 拓扑与角色（实测定案）

| 机器 | 公网 IP | 角色 |
|---|---|---|
| 🇸🇬 新加坡 | 43.156.17.78 | **NovelCraft 生产**（直连 + 本机 443 TLS）|
| 🇺🇸 美国 | 192.227.222.177 | WordPress（发布回执验收）+ 异地加密备份目的地 |
| 🇯🇵 日本 | 199.30.91.54 | 保持 frps（笔记本 Dev 用）；仅当新加坡网络变差再升级为 TLS 前置 |
| 🏠 ASUS 笔记本 | 内网 192.168.31.22 | **仅 Dev**（磁盘 101 IOPS 机械盘，跑不动生产 Postgres）|

- 域名：`novel.xyjin.xyz` → A 记录已解析至 **43.156.17.78**。
- 新加坡端口现状：xray 占 **80 / 8080 / 8443**，**443 空闲**（给 NovelCraft）。
- 关键事实：到 DeepSeek 四台耗时几乎相同（~0.7s），非选型因素；新加坡直连 RTT ~255ms / 丢包 3.3%，对 1–5 人写作工具可接受。

```
浏览器 ──HTTPS(443)──> 新加坡 host nginx ──HTTP──> 127.0.0.1:8090 (前端容器)
                                                     └ 静态 UI + /api → api:8000
```

---

## 1. 全部 VPS：开启 BBR（改善有损链路，一次性）

```bash
echo 'net.core.default_qdisc=fq' | sudo tee -a /etc/sysctl.conf
echo 'net.ipv4.tcp_congestion_control=bbr' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
lsmod | grep bbr        # 有输出即生效
```

---

## 2. 新加坡：系统准备

```bash
# Docker + nginx + certbot
sudo apt update
sudo apt install -y docker.io docker-compose-plugin nginx certbot git
sudo systemctl enable --now docker

# 4G swap（3.6G 内存 + Postgres 必须留兜底，SSD 上）
sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# 确认 443 空、80 被 xray 占
sudo ss -tlnp | grep -E ':80|:443'
```

---

## 3. 新加坡：拉代码 + 配置 .env

```bash
cd /opt && sudo git clone https://github.com/Catatlina/NovelCraft-Personal-Studio.git
cd NovelCraft-Personal-Studio
git checkout agent/remediate-second-audit     # 当前含全部修复的分支（合并到 main 后改用 main）
cp .env.production.example .env
```

编辑 `.env`，按下面填（其余保持默认）：

```bash
NOVELCRAFT_ENV=production
NOVELCRAFT_JWT_SECRET=<执行 openssl rand -hex 32 的结果>
NOVELCRAFT_CREDENTIALS_KEY=<执行 python3 -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())" 的结果>
COOKIE_SECURE=true
COOKIE_SAMESITE=lax
CORS_ORIGINS=https://novel.xyjin.xyz
POSTGRES_PASSWORD=<强密码>
DEEPSEEK_API_KEY=<你的 key，或留空用界面 BYOK>

# 内存兜底：别在 3.6G 上跑本地向量模型（否则 OOM）
EMBEDDING_BACKEND=hash

# Telegram 告警（token 只放这里，不要提交到仓库）
TELEGRAM_BOT_TOKEN=<BotFather 给你的 token>
TELEGRAM_CHAT_ID=8589124694

# 本轮不启用 Sentry / Prometheus
SENTRY_DSN=
METRICS_ENABLED=false

FLOWER_USER=admin
FLOWER_PASSWORD=<强密码>
```

> 生成密钥：
> `openssl rand -hex 32`（JWT）
> `python3 -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"`（Fernet）

---

## 4. 新加坡：签发证书（80 被 xray 占 → 用 DNS-01）

因为 xray 占着 80，HTTP-01 走不通，用 **DNS-01 手动挑战**：

```bash
sudo certbot certonly --manual --preferred-challenges dns -d novel.xyjin.xyz
```
按提示到 xyjin.xyz 的 DNS 处加一条：
```
主机记录: _acme-challenge.novel   类型: TXT   值: <certbot 给出的字符串>
```
生效后回车，证书签发到 `/etc/letsencrypt/live/novel.xyjin.xyz/`。

> **续签**：DNS-01 手动签的证书 90 天到期需重签。若 xyjin.xyz 托管在有 API 的 DNS（Cloudflare / 阿里云 / DNSPod），装对应 `certbot-dns-*` 插件可自动续签；或哪天把 xray 从 80 挪开，改用 `sudo certbot --nginx -d novel.xyjin.xyz` 全自动续签，最省心。

---

## 5. 新加坡：启动应用 + 挂 TLS

```bash
cd /opt/NovelCraft-Personal-Studio

# 启动（前端绑 127.0.0.1:8090 避开 xray 的 80；worker 单进程；跳过 flower）
sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build --scale flower=0
sudo docker compose ps        # api/worker/beat/postgres/redis/frontend 应逐步 healthy

# 挂 host nginx TLS（模板已在仓库）
sudo cp nginx/novelcraft-singapore.conf /etc/nginx/sites-available/novelcraft
sudo sed -i 's/app.example.com/novel.xyjin.xyz/g' /etc/nginx/sites-available/novelcraft
sudo ln -sf /etc/nginx/sites-available/novelcraft /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### ✅ 验收
```bash
curl -s https://novel.xyjin.xyz/api/v1/healthz          # 应含 database:ok redis:ok
```
浏览器打开 `https://novel.xyjin.xyz` → 绿锁 → 注册一个账号 → 能进主界面。
刷新后数据在（持久化 OK）。

---

## 6. Telegram 告警验收（token/chat_id 已就绪）

填好 `.env` 的 `TELEGRAM_*` 后，重启 worker+beat 并测一条：
```bash
sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d worker beat
sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml exec worker \
  python -c "from app.core.alerts import send_alert; print('sent:', send_alert('✅ NovelCraft 告警通道已打通', 'info'))"
```
`sent: True` 且 Telegram 收到 → 通。自动告警场景：预算触顶 / Provider 全失败 / 登录锁定 / 批次失败 / 每 2 小时巡检 / 每日成本日报。

> 安全：token 出现在过对话里，跑通后建议 BotFather `/revoke` 换新 token，改 `.env` 重启即可。

---

## 7. 美国 VPS：WordPress（真实发布回执验收）

代码有 SSRF 硬约束：发布目标必须**公网 HTTPS + 全局 IP**，所以用 VPS 上的 WP。

```bash
# 美国 443 被 xray 占 → 先把 xray 挪到它已有的 8443，腾出 443
# DNS: blog.xyjin.xyz A 记录 → 192.227.222.177
sudo certbot --nginx -d blog.xyjin.xyz          # 美国 80 空闲，HTTP-01 直接可用
# docker 跑 wordpress + mariadb，nginx 反代到它
```
WP 后台 → 用户 → **应用程序密码** → 在 NovelCraft 注册平台账号（Fernet 加密落库、不回显）：
```bash
curl -X POST https://novel.xyjin.xyz/api/v1/publish/account/register \
  -H "Authorization: Bearer <登录后的 access_token>" -H "X-CSRF-Token: <csrf>" \
  -H "Content-Type: application/json" \
  -d '{"platform":"wordpress","account_name":"blog",
       "credentials":{"wp_url":"https://blog.xyjin.xyz","wp_user":"admin","wp_pass":"<应用密码>"}}'
```
发布一篇内容 → 查 `publish_records` 出现真实 `draft_created` + WP 文章 URL = 整链通过。
> Medium 自 2023 起基本不发新 Integration Token，优先用 WordPress 验收。

---

## 8. 异地加密备份（compose 已每日 pg_dump → 推美国）

```bash
# 新加坡装 rclone，配一个到美国 VPS 的 sftp remote（例如叫 us-vps）
sudo apt install -y rclone && rclone config      # 交互式配 sftp: us-vps → 192.227.222.177
# 每日 04:00 同步备份目录
( crontab -l 2>/dev/null; echo "0 4 * * * rclone sync /opt/NovelCraft-Personal-Studio/backups us-vps:/backups/novelcraft" ) | crontab -
```
满足 RPO≤24h。恢复演练：在美国把某个 `.sql.gz` 拉回，`gunzip -c x.sql.gz | psql` 到临时库核对。

---

## 9. 监控现状（本轮口径）

- **Telegram**：✅ 启用（第 6 步）。个人部署最实用的一条。
- **Sentry**：⛔ 本轮不用（`SENTRY_DSN` 留空）。将来想要：sentry.io 免费 DSN 填进 `.env` 重启即可，代码已接。
- **Prometheus `/metrics`**：⛔ 默认关（`METRICS_ENABLED=false`）。要开需同时 `METRICS_ENABLED=true` + `METRICS_TOKEN=<随机>`，抓取端带 `Authorization: Bearer <token>`。

---

## 10. 可选升级：日本 TLS 前置（仅当新加坡网络对你日常用变得难忍）

- 域名 `novel.xyjin.xyz` 改指日本 199.30.91.54；日本 nginx 443 终结 TLS，反代到新加坡。
- **必须**在日本↔新加坡加 **WireGuard 隧道**，否则登录令牌明文过公网；日本 `proxy_pass` 指向新加坡的 WireGuard 内网 IP。
- 纯叠加改动，不需重建应用。需要时按对话记录索取完整 WireGuard + 日本 nginx 配置。

---

## 附：故障排查

| 现象 | 原因 / 处理 |
|---|---|
| `nginx -t` 报证书路径不存在 | 第 4 步 DNS-01 未成功；确认 `/etc/letsencrypt/live/novel.xyjin.xyz/` 有 fullchain.pem |
| 浏览器能开但 /api 502 | 前端容器没起或没绑 8090：`docker compose ps`，确认用了 `-f docker-compose.prod.yml` |
| `send_alert` 返回 False | `.env` 的 `TELEGRAM_*` 没进容器：确认重启带了 `-f docker-compose.prod.yml`（env_file 才生效）|
| 生成时容器被 OOM kill | `EMBEDDING_BACKEND` 没设成 hash（默认会加载本地模型）；确认 swap 已挂 |
| 端口 443 起不来 | xray 或别的进程占了 443：`ss -tlnp | grep :443` 排查 |
| compose 报 `!override` 不认 | Docker 版本过低；升级到 Docker 27+（Compose v2.24+）|

---

## 一页速查（照抄顺序）

```bash
# ① 全 VPS 开 BBR（第 1 节）
# ② 新加坡：装依赖 + swap（第 2 节）
# ③ 拉代码 + 填 .env（第 3 节，域名 novel.xyjin.xyz / CORS / Fernet / JWT / EMBEDDING_BACKEND=hash / Telegram）
# ④ certbot DNS-01 签 novel.xyjin.xyz（第 4 节）
sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build --scale flower=0   # ⑤
sudo cp nginx/novelcraft-singapore.conf /etc/nginx/sites-available/novelcraft
sudo sed -i 's/app.example.com/novel.xyjin.xyz/g' /etc/nginx/sites-available/novelcraft
sudo ln -sf /etc/nginx/sites-available/novelcraft /etc/nginx/sites-enabled/ && sudo nginx -t && sudo systemctl reload nginx
curl -s https://novel.xyjin.xyz/api/v1/healthz     # ⑥ 验收
```
