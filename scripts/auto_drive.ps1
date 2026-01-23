# auto_drive.ps1 - 自动驱动 Function 调用链
#
# 这个脚本启动一个 function 并持续监控，确保调用链完整执行
#
# 用法:
#   .\scripts\auto_drive.ps1 -Function "code_review" -Input "src/ security"
#
# 工作原理:
# 1. 启动 function 执行
# 2. 监控 state.json
# 3. 如果状态是 "running" 但 Claude 已停止，自动发送 "继续" 命令
# 4. 重复直到状态变为 "completed" 或达到最大重试次数

param(
    [Parameter(Mandatory=$true)]
    [string]$Function,
    
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$Input,
    
    [int]$MaxRetries = 10,
    [int]$CheckInterval = 5
)

$StateFile = "scripts/state.json"
$InputStr = $Input -join " "

function Get-State {
    if (Test-Path $StateFile) {
        return Get-Content $StateFile | ConvertFrom-Json
    }
    return $null
}

function Update-State {
    param($Status, $CurrentFunction, $CurrentInput)
    
    $state = @{
        status = $Status
        current_function = $CurrentFunction
        current_input = $CurrentInput
        completed_functions = @()
        last_update = (Get-Date).ToString("o")
    }
    
    $state | ConvertTo-Json | Set-Content $StateFile
}

function Send-Continue {
    Write-Host ""
    Write-Host "⚡ [AUTO-DRIVE] 检测到中断，发送继续命令..." -ForegroundColor Yellow
    Write-Host ""
    
    $prompt = "/continue"
    $prompt | claude --print --continue
}

# ===== 主流程 =====

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "🚀 Auto-Drive: 启动 Function 调用链" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""
Write-Host "Function: $Function" -ForegroundColor White
Write-Host "Input: $InputStr" -ForegroundColor White
Write-Host "Max Retries: $MaxRetries" -ForegroundColor Gray
Write-Host ""

# 初始化状态
Update-State -Status "running" -CurrentFunction $Function -CurrentInput $InputStr

# 启动执行
$prompt = "/fn $Function $InputStr"
Write-Host "📤 发送命令: $prompt" -ForegroundColor Green
Write-Host ""

$prompt | claude --print

# 监控并继续
$retries = 0
while ($retries -lt $MaxRetries) {
    Start-Sleep -Seconds $CheckInterval
    
    $state = Get-State
    
    if ($null -eq $state) {
        Write-Host "⚠️ 状态文件不存在" -ForegroundColor Yellow
        break
    }
    
    if ($state.status -eq "completed") {
        Write-Host ""
        Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
        Write-Host "✅ 调用链已完成！" -ForegroundColor Green
        Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
        break
    }
    
    if ($state.status -eq "running" -and $state.current_function -and $state.current_function -ne "_return") {
        $retries++
        Write-Host ""
        Write-Host "⚠️ 检测到未完成状态 (重试 $retries/$MaxRetries)" -ForegroundColor Yellow
        Write-Host "   当前 function: $($state.current_function)" -ForegroundColor Yellow
        
        Send-Continue
    }
}

if ($retries -ge $MaxRetries) {
    Write-Host ""
    Write-Host "❌ 达到最大重试次数，请手动检查" -ForegroundColor Red
}

Write-Host ""
Write-Host "📊 最终状态:" -ForegroundColor Cyan
Get-State | ConvertTo-Json | Write-Host
