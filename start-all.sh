#!/bin/zsh
# 一键启动 InSight 所有服务（后端 FastAPI :3002 + 前端 React :3000）
# 用法：在项目根目录执行  ./start-all.sh
# 配置：后端读取 server/.env.local（含数据库、端口、LLM 等）

PROJECT_ROOT="${0:A:h}"

echo "========================================="
echo "  启动 InSight 所有服务"
echo "========================================="

# 清理可能残留的旧进程，避免端口冲突
"$PROJECT_ROOT/stop-all.sh" >/dev/null 2>&1 || true

# ── [1/2] 启动后端 ──
echo "\n[1/2] 启动后端服务 (端口 3002)..."
cd "$PROJECT_ROOT/server"
set -a
source .env.local
set +a
nohup .venv/bin/python -m uvicorn app.main:app \
  --host 0.0.0.0 --port 3002 --reload \
  > /tmp/insight-server.log 2>&1 &
echo "  后端日志: /tmp/insight-server.log"

# 等待后端就绪
echo -n "  等待后端就绪"
for i in {1..15}; do
  if curl -sf -o /dev/null http://localhost:3002/health; then
    echo " ✓"
    break
  fi
  echo -n "."
  sleep 1
done
echo ""

# ── [2/2] 启动前端 ──
echo "\n[2/2] 启动前端服务 (端口 3000)..."
cd "$PROJECT_ROOT/web"
nohup npm start > /tmp/insight-web.log 2>&1 &
echo "  前端日志: /tmp/insight-web.log"

echo "\n========================================="
echo "  服务启动中，请稍候..."
echo "========================================="
echo "后端健康: http://localhost:3002/health"
echo "后端管理: http://localhost:3002/admin"
echo "前端界面: http://localhost:3000"
echo "\n查看日志: tail -f /tmp/insight-server.log  /tmp/insight-web.log"
echo "停止服务: ./stop-all.sh"
