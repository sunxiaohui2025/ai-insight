#!/bin/zsh
# 一键停止 InSight 所有服务（后端 FastAPI + 前端 React）

echo "========================================="
echo "  停止 InSight 所有服务"
echo "========================================="

# [1/2] 停止后端 uvicorn
echo "\n[1/2] 停止后端服务..."
if pkill -f "uvicorn app.main:app" 2>/dev/null; then
    echo "  ✓ 后端已停止"
else
    echo "  ⚠ 后端未在运行"
fi

# [2/2] 停止前端 react-scripts
echo "\n[2/2] 停止前端服务..."
if pkill -f "react-scripts" 2>/dev/null; then
    echo "  ✓ 前端已停止"
else
    echo "  ⚠ 前端未在运行"
fi

# 显示端口占用情况（sleep 等待进程退出）
sleep 1
echo "\n检查端口占用："
lsof -i :3002 -i :3000 2>/dev/null || echo "  端口 3002 / 3000 已释放"

echo "\n========================================="
echo "  所有服务已停止"
echo "========================================="
