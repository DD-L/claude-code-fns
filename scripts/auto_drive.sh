#!/bin/bash
# auto_drive.sh - 自动驱动 Function 调用链
#
# 这个脚本启动一个 function 并持续监控，确保调用链完整执行
#
# 用法:
#   ./scripts/auto_drive.sh <function_name> [input...]
#
# 示例:
#   ./scripts/auto_drive.sh code_review src/ security

FUNCTION_NAME="$1"
shift
INPUT="$*"
MAX_RETRIES=10
CHECK_INTERVAL=5
STATE_FILE="scripts/state.json"

if [ -z "$FUNCTION_NAME" ]; then
    echo "用法: $0 <function_name> [input...]"
    exit 1
fi

get_state() {
    if [ -f "$STATE_FILE" ]; then
        cat "$STATE_FILE"
    else
        echo "{}"
    fi
}

get_status() {
    get_state | grep -o '"status": *"[^"]*"' | cut -d'"' -f4
}

get_current_function() {
    get_state | grep -o '"current_function": *"[^"]*"' | cut -d'"' -f4
}

update_state() {
    local status="$1"
    local current_function="$2"
    local current_input="$3"
    
    cat > "$STATE_FILE" << EOF
{
  "status": "$status",
  "current_function": "$current_function",
  "current_input": "$current_input",
  "completed_functions": [],
  "last_update": "$(date -Iseconds)"
}
EOF
}

send_continue() {
    echo ""
    echo "⚡ [AUTO-DRIVE] 检测到中断，发送继续命令..."
    echo ""
    echo "/continue" | claude --print --continue
}

# ===== 主流程 =====

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Auto-Drive: 启动 Function 调用链"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Function: $FUNCTION_NAME"
echo "Input: $INPUT"
echo "Max Retries: $MAX_RETRIES"
echo ""

# 初始化状态
update_state "running" "$FUNCTION_NAME" "$INPUT"

# 启动执行
PROMPT="/fn $FUNCTION_NAME $INPUT"
echo "📤 发送命令: $PROMPT"
echo ""

echo "$PROMPT" | claude --print

# 监控并继续
retries=0
while [ $retries -lt $MAX_RETRIES ]; do
    sleep $CHECK_INTERVAL
    
    status=$(get_status)
    current=$(get_current_function)
    
    if [ "$status" = "completed" ]; then
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "✅ 调用链已完成！"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        break
    fi
    
    if [ "$status" = "running" ] && [ -n "$current" ] && [ "$current" != "_return" ] && [ "$current" != "null" ]; then
        retries=$((retries + 1))
        echo ""
        echo "⚠️ 检测到未完成状态 (重试 $retries/$MAX_RETRIES)"
        echo "   当前 function: $current"
        
        send_continue
    fi
done

if [ $retries -ge $MAX_RETRIES ]; then
    echo ""
    echo "❌ 达到最大重试次数，请手动检查"
fi

echo ""
echo "📊 最终状态:"
get_state
