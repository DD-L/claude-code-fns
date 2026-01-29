<#
.SYNOPSIS
    Function Chain Driver - 使用 headless 模式确保调用链完整执行

.DESCRIPTION
    这个脚本通过循环调用 Claude Code 的 headless 模式来确保 function 调用链完整执行。
    它会监控会话状态文件，在调用链未完成时自动发送继续命令。

.EXAMPLE
    .\scripts\run_chain.ps1 -Function code_review -Input "test_data/sample_code.py security"
    .\scripts\run_chain.ps1 -Function code_review -Input "file.py" -Session test1
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$Function,
    
    [Parameter(Mandatory=$false)]
    [string]$Input = "",
    
    [Parameter(Mandatory=$false)]
    [string]$Session = "default"
)

$StateFile = "scripts/states/$Session.json"
$MaxIterations = 20

function Get-State {
    if (Test-Path $StateFile) {
        try {
            return Get-Content $StateFile -Raw | ConvertFrom-Json
        } catch {
            return $null
        }
    }
    return $null
}

function Reset-State {
    $dir = Split-Path $StateFile -Parent
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    @{ status = "idle"; stack = @(); output = $null } | ConvertTo-Json | Set-Content $StateFile
}

# 初始化
Write-Host "🚀 启动 function 调用链: $Function (session: $Session)" -ForegroundColor Cyan
Write-Host "📝 输入: $Input" -ForegroundColor Gray
Write-Host ("=" * 50)

# 重置状态
Reset-State

# 初始命令
$prompt = "/fn $Function $Input --session=$Session"

for ($i = 1; $i -le $MaxIterations; $i++) {
    Write-Host "`n--- 迭代 $i ---" -ForegroundColor Yellow
    
    # 使用 claude headless 模式执行
    try {
        $result = & claude -p $prompt --output-format json 2>&1
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "❌ 执行失败: $result" -ForegroundColor Red
            break
        }
    } catch {
        Write-Host "❌ 执行异常: $_" -ForegroundColor Red
        break
    }
    
    # 检查状态
    $state = Get-State
    
    if ($null -eq $state) {
        Write-Host "⚠️ 无法读取状态文件" -ForegroundColor Yellow
        break
    }
    
    if ($state.status -eq "idle" -and $state.stack.Count -eq 0) {
        Write-Host ("=" * 50)
        Write-Host "✅ 调用链完成" -ForegroundColor Green
        if ($state.output) {
            Write-Host "输出: $($state.output)" -ForegroundColor Gray
        }
        break
    }
    elseif ($state.status -eq "running" -and $state.stack.Count -gt 0) {
        $topFn = $state.stack[-1].function
        $prompt = "/fn_continue --session=$Session"
        Write-Host "🔄 继续: $topFn (depth: $($state.stack.Count))" -ForegroundColor Cyan
    }
    else {
        Write-Host "⚠️ 状态异常，停止执行" -ForegroundColor Yellow
        Write-Host "状态: $($state | ConvertTo-Json -Compress)" -ForegroundColor Gray
        break
    }
    
    # 短暂延迟，避免过快调用
    Start-Sleep -Milliseconds 500
}

if ($i -gt $MaxIterations) {
    Write-Host "⚠️ 达到最大迭代次数 ($MaxIterations)" -ForegroundColor Yellow
}
