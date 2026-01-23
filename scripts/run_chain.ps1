<#
.SYNOPSIS
    Function Chain Driver - 使用 headless 模式确保调用链完整执行

.DESCRIPTION
    这个脚本通过循环调用 Claude Code 的 headless 模式来确保 function 调用链完整执行。
    它会监控 state.json 文件，在调用链未完成时自动发送继续命令。

.EXAMPLE
    .\scripts\run_chain.ps1 -Function code_review -Input "test_data/sample_code.py security"
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$Function,
    
    [Parameter(Mandatory=$false)]
    [string]$Input = ""
)

$StateFile = "scripts/state.json"
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
    @{
        status = "idle"
        current_function = $null
        completed_functions = @()
        last_update = (Get-Date).ToString("o")
    } | ConvertTo-Json | Set-Content $StateFile
}

# 初始化
Write-Host "🚀 启动 function 调用链: $Function" -ForegroundColor Cyan
Write-Host "📝 输入: $Input" -ForegroundColor Gray
Write-Host ("=" * 50)

# 重置状态
Reset-State

# 初始命令
$prompt = "/fn $Function $Input"

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
    
    if ($state.status -eq "completed") {
        Write-Host ("=" * 50)
        Write-Host "✅ 调用链完成" -ForegroundColor Green
        if ($state.completed_functions) {
            Write-Host "执行路径: $($state.completed_functions -join ' → ')" -ForegroundColor Gray
        }
        break
    }
    elseif ($state.status -eq "running" -and $state.current_function) {
        # 继续执行
        $prompt = "继续执行 function 调用链，当前: $($state.current_function)"
        Write-Host "🔄 继续: $($state.current_function)" -ForegroundColor Cyan
    }
    else {
        Write-Host "⚠️ 状态异常，停止执行" -ForegroundColor Yellow
        Write-Host "状态: $($state | ConvertTo-Json)" -ForegroundColor Gray
        break
    }
    
    # 短暂延迟，避免过快调用
    Start-Sleep -Milliseconds 500
}

if ($i -gt $MaxIterations) {
    Write-Host "⚠️ 达到最大迭代次数 ($MaxIterations)" -ForegroundColor Yellow
}
