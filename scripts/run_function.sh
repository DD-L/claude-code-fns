#!/bin/bash
# run_function.sh - 在 headless 模式下启动一个 function
#
# 用法:
#   ./scripts/run_function.sh <function_name> [input...]
#
# 示例:
#   ./scripts/run_function.sh code_review src/ security

FUNCTION_NAME="$1"
shift
INPUT="$*"

if [ -z "$FUNCTION_NAME" ]; then
    echo "Usage: $0 <function_name> [input...]"
    echo ""
    echo "Available functions:"
    ls -1 functions/*.json 2>/dev/null | xargs -I{} basename {} .json | grep -v "^_"
    exit 1
fi

FUNCTION_FILE="functions/${FUNCTION_NAME}.json"

if [ ! -f "$FUNCTION_FILE" ]; then
    echo "❌ Function not found: $FUNCTION_NAME"
    echo "   Expected file: $FUNCTION_FILE"
    exit 1
fi

echo "🚀 Starting function: $FUNCTION_NAME"
echo "   Input: $INPUT"
echo ""

# 构建执行提示
PROMPT="/fn $FUNCTION_NAME $INPUT"

# 使用 Claude Code headless 模式执行
echo "$PROMPT" | claude --print

echo ""
echo "✅ Function execution initiated"
