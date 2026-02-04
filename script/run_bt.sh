#!/bin/bash
# 宝塔面板计划任务包装脚本
# 用法：直接在宝塔计划任务中执行此脚本 bash /path/to/script/run_bt.sh

# 获取脚本所在目录的上一级目录（项目根目录）
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR" || exit 1

# 加载环境变量
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# 强制设置运行模式为单次运行（交由宝塔计划任务调度）
export RUN_MODE="once"

# 检查是否存在虚拟环境
if [ -d "venv" ]; then
    source venv/bin/activate
    PYTHON_CMD="venv/bin/python3"
elif [ -d ".venv" ]; then
    source .venv/bin/activate
    PYTHON_CMD=".venv/bin/python3"
else
    # 尝试使用系统 python3
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    else
        PYTHON_CMD="python"
    fi
fi

echo "当前时间: $(date)"
echo "项目目录: $PROJECT_DIR"
echo "使用 Python: $PYTHON_CMD"

# 运行签到脚本
# 使用 -u 参数禁用缓冲，确保日志实时输出
$PYTHON_CMD -u rainyun.py

echo "执行结束"
