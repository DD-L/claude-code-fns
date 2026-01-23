# check_and_continue.ps1 - Stop-Hook 脚本
#
# 这个脚本检查 function 执行状态
# 如果调用链未完成，输出继续执行的指令

$StateFile = "scripts/state.json"

# 检查状态文件是否存在
if (-not (Test-Path $StateFile)) {
    Write-Host "状态文件不存在，无需继续"
    exit 0
}

# 读取状态
$State = Get-Content $StateFile | ConvertFrom-Json

$Status = $State.status
$Current = $State.current_function

# 检查是否需要继续
if ($Status -eq "running" -and $Current -and $Current -ne "null" -and $Current -ne "_return") {
    Write-Host ""
    Write-Host "⚠️ [STOP-HOOK] 检测到未完成的调用链！" -ForegroundColor Red
    Write-Host ""
    Write-Host "当前 function: $Current" -ForegroundColor Yellow
    Write-Host "状态: $Status" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
    Write-Host "⚡ 强制继续执行: 请立即执行 $Current" -ForegroundColor Cyan
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "你必须继续执行 function 调用链，不能停止。"
} else {
    Write-Host "调用链已完成或无待执行任务"
}
