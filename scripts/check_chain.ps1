<#
.SYNOPSIS
    Stop Hook - 检查 function 调用链是否需要继续

.DESCRIPTION
    这个脚本作为 Claude Code 的 Stop hook 运行。
    当 Claude 准备停止响应时，检查调用链是否完成。
    如果未完成，输出提示让 Claude 继续执行。
#>

$StateFile = "scripts/state.json"

# 读取状态
if (-not (Test-Path $StateFile)) {
    exit 0
}

try {
    $state = Get-Content $StateFile -Raw | ConvertFrom-Json
} catch {
    exit 0
}

# 检查是否需要继续
if ($state.status -eq "running" -and $state.current_function -and $state.current_function -ne "_return") {
    $nextFn = $state.current_function
    
    # 输出到 stdout - Claude 会看到这个并继续执行
    Write-Output ""
    Write-Output "=================================================="
    Write-Output "[STOP-HOOK] Function chain is NOT complete!"
    Write-Output "Current function: $nextFn"
    Write-Output "You MUST continue executing. Do NOT stop here."
    Write-Output "=================================================="
    Write-Output ""
    
    # 非零退出码会阻止 Claude 停止
    exit 1
}

exit 0
