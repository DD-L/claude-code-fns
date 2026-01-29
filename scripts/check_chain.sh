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

STATE_FILE="$STATES_DIR/$WT_SESSION.json"
echo "[$TIMESTAMP] Checking state file: $STATE_FILE" >> "$LOG_FILE"

if [ ! -f "$STATE_FILE" ]; then
    echo "[$TIMESTAMP] State file not found, allowing stop" >> "$LOG_FILE"
    exit 0
fi

# 解析状态文件
STATE_CONTENT=$(cat "$STATE_FILE")

# 检查 status 是否为 "running"
STATUS=$(echo "$STATE_CONTENT" | grep -o '"status"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"\([^"]*\)"$/\1/')

# 检查 stack 是否非空（简单判断：stack 数组中有内容）
STACK_EMPTY=$(echo "$STATE_CONTENT" | grep -o '"stack"[[:space:]]*:[[:space:]]*\[\]')

if [ "$STATUS" = "running" ] && [ -z "$STACK_EMPTY" ]; then
    echo "[$TIMESTAMP] Stack NOT empty! Blocking stop." >> "$LOG_FILE"
    
    # 提取栈深度和栈顶函数（简单解析）
    DEPTH=$(echo "$STATE_CONTENT" | grep -o '"function"' | wc -l)
    TOP_FUNC=$(echo "$STATE_CONTENT" | grep -o '"function"[[:space:]]*:[[:space:]]*"[^"]*"' | tail -1 | sed 's/.*"\([^"]*\)"$/\1/')
    
    # 单复数处理
    FRAME_WORD="frame"
    if [ "$DEPTH" -gt 1 ]; then
        FRAME_WORD="frames"
    fi
    
    # 构建输出消息
    {
        echo "[STOP-HOOK] Stack NOT empty ($DEPTH $FRAME_WORD)"
        echo "Top: $TOP_FUNC"
        
        # 尝试用 jq 提取更多信息（如果可用）
        if command -v jq &> /dev/null; then
            TOP_ARGS=$(echo "$STATE_CONTENT" | jq -c '.stack[-1].args // empty' 2>/dev/null)
            if [ -n "$TOP_ARGS" ]; then
                echo "Args: $TOP_ARGS"
            fi
            
            # 显示栈追踪（最多5个）
            if [ "$DEPTH" -gt 1 ]; then
                echo "Stack (bottom to top):"
                SHOW_COUNT=$((DEPTH < 5 ? DEPTH : 5))
                START_IDX=$((DEPTH - SHOW_COUNT))
                if [ "$START_IDX" -gt 0 ]; then
                    echo "  ... ($START_IDX more)"
                fi
                for i in $(seq $START_IDX $((DEPTH - 1))); do
                    FUNC=$(echo "$STATE_CONTENT" | jq -r ".stack[$i].function" 2>/dev/null)
                    if [ "$i" -eq $((DEPTH - 1)) ]; then
                        echo "  [$i] $FUNC <- TOP"
                    else
                        echo "  [$i] $FUNC"
                    fi
                done
            fi
        fi
        
        echo "You MUST continue until stack is empty. Run: /fn_continue"
    } >&2
    exit 2
fi

echo "[$TIMESTAMP] Stack empty or not running, allowing stop" >> "$LOG_FILE"
exit 0
