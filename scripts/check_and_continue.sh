#!/bin/bash
# check_and_continue.sh - Stop-Hook 脚本
#
# 这个脚本被 skill 调用，检查 function 执行状态
# 如果调用链未完成，输出继续执行的指令
#
# 用法（在 skill 中）:
#   $run_bash(./scripts/check_and_continue.sh)

STATE_FILE="scripts/state.json"

# 检查状态文件是否存在
if [ ! -f "$STATE_FILE" ]; then
    echo "状态文件不存在，无需继续"
    exit 0
fi

# 读取状态
STATUS=$(cat "$STATE_FILE" | grep -o '"status": *"[^"]*"' | cut -d'"' -f4)
CURRENT=$(cat "$STATE_FILE" | grep -o '"current_function": *"[^"]*"' | cut -d'"' -f4)
PENDING=$(cat "$STATE_FILE" | grep -o '"pending_functions": *\[[^]]*\]')

# 检查是否需要继续
if [ "$STATUS" = "running" ] && [ -n "$CURRENT" ] && [ "$CURRENT" != "null" ] && [ "$CURRENT" != "_return" ]; then
    echo ""
    echo "⚠️ [STOP-HOOK] 检测到未完成的调用链！"
    echo ""
    echo "当前 function: $CURRENT"
    echo "状态: $STATUS"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "⚡ 强制继续执行: 请立即执行 $CURRENT"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "你必须继续执行 function 调用链，不能停止。"
else
    echo "调用链已完成或无待执行任务"
fi
