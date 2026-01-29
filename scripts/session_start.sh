#!/bin/bash
#
# SessionStart Hook - 记录会话启动
#
# 记录 Claude Code 会话启动信息。
# 主要的会话 ID 获取逻辑在 fn 命令中通过 WT_SESSION 实现。

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATES_DIR="$SCRIPT_DIR/states"

# 确保 states 目录存在
mkdir -p "$STATES_DIR"

# 从 stdin 读取 JSON
INPUT_JSON=$(cat)

# 调试日志
LOG_FILE="$STATES_DIR/.hook_debug.log"
TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")

echo "[$TIMESTAMP] SessionStart hook triggered" >> "$LOG_FILE"
echo "[$TIMESTAMP] WT_SESSION: $WT_SESSION" >> "$LOG_FILE"
echo "[$TIMESTAMP] Input length: ${#INPUT_JSON}" >> "$LOG_FILE"
echo "[$TIMESTAMP] CLAUDE_ENV_FILE: $CLAUDE_ENV_FILE" >> "$LOG_FILE"

exit 0
