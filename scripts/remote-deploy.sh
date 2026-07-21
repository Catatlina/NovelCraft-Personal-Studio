#!/bin/bash
# ═══════════════════════════════════════
# VPS 一键部署命令
# 在 VPS 上执行:
#   curl -sSL https://raw.githubusercontent.com/Catatlina/NovelCraft-Personal-Studio/starlume-v2/scripts/remote-deploy.sh | bash
# ═══════════════════════════════════════

set -e

REPO="https://github.com/Catatlina/NovelCraft-Personal-Studio.git"
BRANCH="starlume-v2"
APP_DIR="$HOME/starlume-v2"

echo "🚀 星禾 AI · 远程一键部署"
echo "=========================="

# 1. 安装 Docker (如未安装)
if ! command -v docker &>/dev/null; then
    echo "📦 安装 Docker..."
    curl -fsSL https://get.docker.com | bash
    sudo systemctl enable docker
    sudo systemctl start docker
fi

# 2. 克隆或更新代码
if [ -d "$APP_DIR/.git" ]; then
    echo "📥 更新代码..."
    cd "$APP_DIR"
    git fetch origin
    git reset --hard "origin/$BRANCH"
else
    echo "📥 克隆代码..."
    git clone -b "$BRANCH" "$REPO" "$APP_DIR"
    cd "$APP_DIR"
fi

# 3. 部署
echo "🐳 构建并启动..."
cd "$APP_DIR"
docker compose down 2>/dev/null || true
docker compose build --no-cache
docker compose up -d

# 4. 等待就绪
echo "⏳ 等待服务就绪..."
sleep 5
for i in $(seq 1 15); do
    if curl -s http://localhost:8000/api/v1/healthz >/dev/null 2>&1; then
        echo "✅ 服务就绪"
        break
    fi
    sleep 2
done

echo ""
echo "✅ 部署完成！"
echo "📍 本地访问: http://localhost:8090"
echo "🔍 健康检查: curl http://localhost:8000/api/v1/healthz"
echo "📊 查看日志: docker compose logs -f"
