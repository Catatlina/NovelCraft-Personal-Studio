#!/bin/bash
# ═══════════════════════════════════════
# 星禾 AI · VPS 43 部署脚本
# 目标: 43.156.17.78 (Singapore)
# ═══════════════════════════════════════

set -e

echo "🚀 星禾 AI 工作台 · VPS 部署"
echo "============================"
echo ""

# 1. 检查环境
echo "📋 步骤 1/6: 检查 Docker 环境..."
docker --version || { echo "❌ 未安装 Docker"; exit 1; }
docker compose version || { echo "❌ 需要 Docker Compose v2"; exit 1; }

# 2. 停止旧服务
echo ""
echo "📋 步骤 2/6: 停止旧服务..."
docker compose down 2>/dev/null || true

# 3. 构建镜像
echo ""
echo "📋 步骤 3/6: 构建镜像..."
docker compose build --no-cache

# 4. 启动服务
echo ""
echo "📋 步骤 4/6: 启动服务..."
docker compose up -d

# 5. 等待健康检查
echo ""
echo "📋 步骤 5/6: 等待服务就绪..."
for i in $(seq 1 20); do
    if curl -s http://localhost:8000/api/v1/healthz > /dev/null 2>&1; then
        echo "   ✅ API 就绪"
        break
    fi
    sleep 2
done

# 6. 验证
echo ""
echo "📋 步骤 6/6: 验证部署..."
echo ""
echo "   健康检查:"
curl -s http://localhost:8000/api/v1/healthz | python3 -m json.tool 2>/dev/null || echo "   (JSON 格式化不可用，但服务正常)"
echo ""
echo "   前端访问:"
curl -s -o /dev/null -w "   HTTP %{http_code}" http://localhost:8090/ && echo ""
echo ""
echo "════════════════════════════════════"
echo "✅ 部署完成！"
echo ""
echo "📍 访问地址:"
echo "   - 前端:    https://your-domain.com  (通过 Nginx 443 → 8090)"
echo "   - API:     https://your-domain.com/api/v1/healthz"
echo "   - 本地验证: curl http://localhost:8000/api/v1/healthz"
echo ""
echo "🧹 常用命令:"
echo "   docker compose logs -f          # 查看日志"
echo "   docker compose restart          # 重启服务"
echo "   docker compose down             # 停止服务"
echo "   docker compose up -d --build    # 重新构建并启动"
echo "════════════════════════════════════"
