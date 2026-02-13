#!/bin/bash
#
# Stop Hook - 检查当前 Windows Terminal 会话的调用链是否需要继续
#
# 使用 WT_SESSION 环境变量（Windows Terminal 窗口级持久 ID）
# 仅当当前会话的 stack 非空时才阻止停止。
#
# 根据 Claude Code Hooks 文档:
# - exit 0: 允许停止
# - exit 2 + stderr: 阻止停止，stderr 内容反馈给 Claude

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATES_DIR="$SCRIPT_DIR/states"

# 确保目录存在
if [ ! -d "$STATES_DIR" ]; then
    exit 0
fi

# 调试日志
LOG_FILE="$STATES_DIR/.hook_debug.log"
TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")

# 从 stdin 读取 JSON
INPUT_JSON=$(cat)

echo "[$TIMESTAMP] Stop hook triggered" >> "$LOG_FILE"
echo "[$TIMESTAMP] WT_SESSION: $WT_SESSION" >> "$LOG_FILE"
echo "[$TIMESTAMP] Input: $INPUT_JSON" >> "$LOG_FILE"

# 解析 stdin 中的 stop_hook_active（使用简单的 grep/sed）
STOP_HOOK_ACTIVE=""
if [ -n "$INPUT_JSON" ]; then
    STOP_HOOK_ACTIVE=$(echo "$INPUT_JSON" | grep -o '"stop_hook_active"[[:space:]]*:[[:space:]]*true' | head -1)
fi

# 防止无限循环
if [ -n "$STOP_HOOK_ACTIVE" ]; then
    echo "[$TIMESTAMP] stop_hook_active=true, allowing stop" >> "$LOG_FILE"
    exit 0
fi

# 使用 WT_SESSION 作为会话标识符
if [ -z "$WT_SESSION" ]; then
    echo "[$TIMESTAMP] No WT_SESSION, allowing stop" >> "$LOG_FILE"
    exit 0
fi

STATE_FILE="$STATES_DIR/$WT_SESSION/state.json"
echo "[$TIMESTAMP] Checking state file: $STATE_FILE" >> "$LOG_FILE"

if [ ! -f "$STATE_FILE" ]; then
    echo "[$TIMESTAMP] State file not found, allowing stop" >> "$LOG_FILE"
    exit 0
fi

# 解析状态文件
STATE_CONTENT=$(cat "$STATE_FILE")

# 检查 status
STATUS=$(echo "$STATE_CONTENT" | grep -o '"status"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"\([^"]*\)"$/\1/')
if [ -z "$STATUS" ]; then
    STATUS="idle"
fi

# 检查栈深度（忽略 status - 检测栈泄漏即使 status=idle）
DEPTH=$(echo "$STATE_CONTENT" | grep -o '"function"' | wc -l)

# 始终记录状态信息用于审计
echo "[$TIMESTAMP] State: status=$STATUS, depth=$DEPTH" >> "$LOG_FILE"

if [ "$DEPTH" -gt 0 ]; then
    # 提取栈顶函数
    TOP_FUNC=$(echo "$STATE_CONTENT" | grep -o '"function"[[:space:]]*:[[:space:]]*"[^"]*"' | tail -1 | sed 's/.*"\([^"]*\)"$/\1/')
    
    # 栈泄漏警告（idle 但 depth > 0）
    LEAK_NOTE=""
    if [ "$STATUS" = "idle" ]; then
        echo "[$TIMESTAMP] WARNING: Stack leak detected! status=idle but depth=$DEPTH" >> "$LOG_FILE"
        LEAK_NOTE=" [LEAK]"
    fi
    
    echo "[$TIMESTAMP] Stack NOT empty! Blocking stop." >> "$LOG_FILE"
    echo "[$TIMESTAMP]   Top frame: $TOP_FUNC" >> "$LOG_FILE"
    
    # Log call chain if jq available
    CHAIN=""
    if command -v jq &> /dev/null && [ "$DEPTH" -gt 1 ]; then
        CHAIN=$(echo "$STATE_CONTENT" | jq -r '[.stack[].function] | join(" → ")' 2>/dev/null)
        if [ -n "$CHAIN" ]; then
            echo "[$TIMESTAMP]   Call chain: $CHAIN" >> "$LOG_FILE"
        fi
    fi
    
    # Build top frame with args
    TOP_WITH_ARGS="$TOP_FUNC"
    if command -v jq &> /dev/null; then
        TOP_ARGS=$(echo "$STATE_CONTENT" | jq -r '.stack[-1].args // {} | to_entries | map("\(.key)=\(.value)") | join(", ")' 2>/dev/null)
        if [ -n "$TOP_ARGS" ] && [ "$TOP_ARGS" != "" ]; then
            TOP_WITH_ARGS="$TOP_FUNC ($TOP_ARGS)"
        fi
    fi
    
    # Build call chain (max 5 frames)
    CHAIN_DISPLAY=""
    if command -v jq &> /dev/null; then
        if [ "$DEPTH" -le 5 ]; then
            CHAIN_DISPLAY=$(echo "$STATE_CONTENT" | jq -r '[.stack[].function] | join(" → ")' 2>/dev/null)
        else
            # Show ... → last 5
            CHAIN_DISPLAY=$(echo "$STATE_CONTENT" | jq -r '"... → " + ([.stack[-5:][].function] | join(" → "))' 2>/dev/null)
        fi
    else
        # Fallback without jq
        CHAIN_DISPLAY="$TOP_FUNC"
    fi
    
    # 构建用户友好的输出消息
    {
        echo "[!][STOP-HOOK] Cannot stop: Stack not empty$LEAK_NOTE"
        echo "  Session: $WT_SESSION"
        echo "  Stack depth: $DEPTH"
        echo "  Top frame: $TOP_WITH_ARGS"
        echo "  Call chain: $CHAIN_DISPLAY"
        echo "  To continue: /fn_continue --session=$WT_SESSION"
    } >&2
    exit 2
fi

# Task complete - output brief info
OUTPUT_INFO=""
if command -v jq &> /dev/null; then
    OUTPUT_VAL=$(echo "$STATE_CONTENT" | jq -r '.output // empty' 2>/dev/null)
    if [ -n "$OUTPUT_VAL" ]; then
        # Truncate if too long
        if [ ${#OUTPUT_VAL} -gt 100 ]; then
            OUTPUT_VAL="${OUTPUT_VAL:0:97}..."
        fi
        OUTPUT_INFO=" | output: $OUTPUT_VAL"
    fi
fi

echo "[$TIMESTAMP] Stack empty (depth=0), allowing stop" >> "$LOG_FILE"

# Brief completion message to stderr (informational, still exit 0)
echo "[ok] $WT_SESSION | idle$OUTPUT_INFO" >&2
exit 0
