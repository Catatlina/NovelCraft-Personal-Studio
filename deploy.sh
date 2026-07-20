#!/bin/bash
# 星禾AI工作台 · 一键部署脚本
# 在你的 Mac 本地终端执行: bash deploy.sh

set -e
SERVER="root@43.156.17.78"
DOMAIN="novel.xyjin.xyz"

echo "🚀 部署星禾AI工作台到 $DOMAIN"

echo "1/3 同步代码..."
ssh $SERVER "cd /root/NovelCraft-Personal-Studio && git stash && git pull origin main --rebase"

echo "2/3 重建容器..."
ssh $SERVER "cd /root/NovelCraft-Personal-Studio && docker compose down && docker compose up -d --build"

echo "3/3 等待启动..."
sleep 5
ssh $SERVER "cd /root/NovelCraft-Personal-Studio && docker compose ps"

echo "✅ 部署完成 https://$DOMAIN"
