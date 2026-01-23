#!/bin/bash
# drive.sh - 驱动 Claude Code 继续执行未完成的 function
#
# 用法:
#   ./scripts/drive.sh                    # 发送 "继续"
#   ./scripts/drive.sh "custom prompt"    # 发送自定义提示
#
# 这个脚本通过 Claude Code 的 headless 模式实现 stop-hook 机制

PROMPT="${1:-继续执行当前 function，从上次停止的地方继续}"

echo "🔄 Driving Claude Code to continue..."
echo "   Prompt: $PROMPT"
echo ""

# 使用 Claude Code headless 模式
echo "$PROMPT" | claude --print --continue 2>/dev/null

# 检查退出状态
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Drive completed"
else
    echo ""
    echo "⚠️  Claude Code exited with non-zero status"
    echo "   You may need to run this script again or check the logs"
fi
