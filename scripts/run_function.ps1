# run_function.ps1 - 在 headless 模式下启动一个 function
#
# 用法:
#   .\scripts\run_function.ps1 <function_name> [input...]
#
# 示例:
#   .\scripts\run_function.ps1 code_review src/ security

param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$FunctionName,
    
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$Input
)

$FunctionFile = "functions\$FunctionName.json"

if (-not (Test-Path $FunctionFile)) {
    Write-Host "❌ Function not found: $FunctionName" -ForegroundColor Red
    Write-Host "   Expected file: $FunctionFile" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Available functions:" -ForegroundColor Cyan
    Get-ChildItem functions\*.json | 
        Where-Object { $_.Name -notlike '_*' } | 
        ForEach-Object { Write-Host "  - $($_.BaseName)" }
    exit 1
}

$InputStr = $Input -join " "

Write-Host "🚀 Starting function: $FunctionName" -ForegroundColor Cyan
Write-Host "   Input: $InputStr" -ForegroundColor Gray
Write-Host ""

# 构建执行提示
$Prompt = "/fn $FunctionName $InputStr"

# 使用 Claude Code headless 模式执行
$Prompt | claude --print

Write-Host ""
Write-Host "✅ Function execution initiated" -ForegroundColor Green
