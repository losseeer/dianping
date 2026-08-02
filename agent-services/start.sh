#!/bin/bash
# 启动 Agent 微服务脚本 — 使用 conda Python 环境
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$HOME/miniconda3/bin/python3"

# 检查 conda Python
if [ ! -f "$PYTHON" ]; then
    echo "Error: conda Python not found at $PYTHON"
    echo "  Install miniconda or update PYTHON path in this script."
    exit 1
fi

# 检查各 Agent 的 .env 文件
for agent in agent1 agent2; do
    if [ ! -f "$SCRIPT_DIR/$agent/.env" ]; then
        echo "Warning: $agent/.env not found. Copying from .env.example"
        cp "$SCRIPT_DIR/$agent/.env.example" "$SCRIPT_DIR/$agent/.env"
        echo "  Please edit $agent/.env and fill in your values."
    fi
done

# 从各自目录启动
echo "Starting Agent1 (Review Summary)..."
cd "$SCRIPT_DIR/agent1"
AGENT1_PORT=$(grep AGENT1_PORT .env | cut -d= -f2 || echo 8001)
$PYTHON main.py &
AGENT1_PID=$!

echo "Starting Agent2 (Shop Recommendation)..."
cd "$SCRIPT_DIR/agent2"
AGENT2_PORT=$(grep AGENT2_PORT .env | cut -d= -f2 || echo 8002)
$PYTHON main.py &
AGENT2_PID=$!

echo ""
echo "Both agents are running:"
echo "  Agent1: http://localhost:$AGENT1_PORT"
echo "  Agent2: http://localhost:$AGENT2_PORT"
echo ""
echo "Press Ctrl+C to stop both."

trap "kill $AGENT1_PID $AGENT2_PID 2>/dev/null; echo 'Agents stopped.'" EXIT INT TERM

wait
