#!/bin/bash
# scripts/wait_for_status.sh - 等待交互脚本状态变化
# 用途：等待 agent_output.txt 出现新轮次或完成标记
#
# 用法：
#   scripts/wait_for_status.sh [<output_file>]
#
# 如果未指定 <output_file>，则自动调用 get_session_id.py 获取会话 ID
# 后使用路径：scripts/states/<SESSION_ID>/agent_output.txt

# 检测 python 命令（兼容 python3 和 python）
if command -v python3 &> /dev/null; then
    PYTHON_CMD=python3
else
    PYTHON_CMD=python
fi

# 获取脚本所在目录（确保正确调用 get_session_id.py）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 获取输出文件路径与会话 ID
OUTPUT_FILE="${1:-}"
if [ -z "$OUTPUT_FILE" ]; then
    # 自动获取会话 ID（与 interactive_wrapper 一致：get_session_id.py，空则 default）
    SESSION_ID=$($PYTHON_CMD "$SCRIPT_DIR/get_session_id.py" --format raw 2>/dev/null)
    SESSION_ID="${SESSION_ID:-default}"
    OUTPUT_FILE="$SCRIPT_DIR/states/${SESSION_ID}/agent_output.txt"
else
    # 已指定 output 文件时，从路径推出 session（states/<session>/agent_output.txt）
    SESSION_ID=$(basename "$(dirname "$OUTPUT_FILE")")
fi

# 等待新轮次或完成标记
while ! grep -q "^=== CC_FN_TURN [0-9]\+ ===\|^=== CC_FN_COMPLETE ===" "$OUTPUT_FILE" 2>/dev/null; do
  sleep 0.5
done

# 首行输出 AI 写入路径，执行流程中无需再主动获取 session
echo "CC_FN_AGENT_INPUT_PATH=scripts/states/${SESSION_ID}/agent_input.txt"
# 随后输出本次轮次/完成内容
cat "$OUTPUT_FILE"
