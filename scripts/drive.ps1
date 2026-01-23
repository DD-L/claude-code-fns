# drive.ps1 - 驱动 Claude Code 继续执行未完成的 function
#
# 用法:
#   .\scripts\drive.ps1                    # 发送 "继续"
#   .\scripts\drive.ps1 "custom prompt"    # 发送自定义提示
#
# 这个脚本通过 Claude Code 的 headless 模式实现 stop-hook 机制

param(
    [string]$Prompt = "继续执行当前 function，从上次停止的地方继续"
)

Write-Host "🔄 Driving Claude Code to continue..." -ForegroundColor Cyan
Write-Host "   Prompt: $Prompt" -ForegroundColor Gray
Write-Host ""

# 使用 Claude Code headless 模式
$Prompt | claude --print --continue

# 检查退出状态
if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ Drive completed" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "⚠️  Claude Code exited with non-zero status" -ForegroundColor Yellow
    Write-Host "   You may need to run this script again or check the logs" -ForegroundColor Gray
}
