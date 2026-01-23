# test_demo.ps1
# 演示如何使用各个 function 的示例脚本
#
# 这个脚本展示了如何实际调用每个 function，适合手动测试和演示

param(
    [ValidateSet("all", "task_orchestrator", "code_review", "fix_issues", "run_tests", "demo_chain")]
    [string]$Demo = "all"
)

$ErrorActionPreference = "Continue"

function Write-DemoHeader {
    param([string]$Message)
    Write-Host "`n" -NoNewline
    Write-Host "╔" + ("═" * 78) + "╗" -ForegroundColor Cyan
    Write-Host "║  $Message" -ForegroundColor Cyan
    Write-Host "╚" + ("═" * 78) + "╝" -ForegroundColor Cyan
}

function Write-DemoStep {
    param([string]$Message)
    Write-Host "`n  📌 $Message" -ForegroundColor Yellow
}

function Invoke-FunctionDemo {
    param(
        [string]$FunctionName,
        [string]$Input
    )
    
    Write-DemoStep "执行: /fn $FunctionName $Input"
    Write-Host "    命令: /fn $FunctionName $Input" -ForegroundColor Gray
    
    # 实际调用 run_function.ps1
    if (Test-Path "scripts\run_function.ps1") {
        & .\scripts\run_function.ps1 $FunctionName $Input
    } else {
        Write-Host "    ⚠️  脚本 scripts\run_function.ps1 不存在，请手动执行:" -ForegroundColor Yellow
        Write-Host "       /fn $FunctionName $Input" -ForegroundColor White
    }
}

# Demo 1: task_orchestrator
function Demo-TaskOrchestrator {
    Write-DemoHeader "Demo 1: task_orchestrator - 智能任务编排"
    
    Write-Host "`n  这个 function 会分析任务并路由到合适的 function。" -ForegroundColor White
    Write-Host "  让我们测试几个不同的任务类型：" -ForegroundColor White
    
    # 测试路由到 code_review
    Write-DemoStep "测试 1: 代码审查任务"
    Invoke-FunctionDemo "task_orchestrator" "请审查 test_data/sample_code.py 的安全性"
    
    Start-Sleep -Seconds 2
    
    # 测试路由到 fix_issues
    Write-DemoStep "测试 2: 代码修复任务"
    Invoke-FunctionDemo "task_orchestrator" "修复 test_data 目录中的代码问题"
    
    Start-Sleep -Seconds 2
    
    # 测试路由到 run_tests
    Write-DemoStep "测试 3: 测试任务"
    Invoke-FunctionDemo "task_orchestrator" "运行测试验证代码功能"
}

# Demo 2: code_review
function Demo-CodeReview {
    Write-DemoHeader "Demo 2: code_review - 代码审查"
    
    Write-Host "`n  这个 function 会审查代码的质量、安全性和性能问题。" -ForegroundColor White
    
    # 安全审查
    Write-DemoStep "测试 1: 安全审查 Python 代码"
    Invoke-FunctionDemo "code_review" "test_data/sample_code.py security"
    
    Start-Sleep -Seconds 2
    
    # 性能审查
    Write-DemoStep "测试 2: 性能审查 JavaScript 代码"
    Invoke-FunctionDemo "code_review" "test_data/sample_code.js performance"
    
    Start-Sleep -Seconds 2
    
    # 质量审查
    Write-DemoStep "测试 3: 全面质量审查"
    Invoke-FunctionDemo "code_review" "test_data/ quality"
}

# Demo 3: fix_issues
function Demo-FixIssues {
    Write-DemoHeader "Demo 3: fix_issues - 修复代码问题"
    
    Write-Host "`n  这个 function 会根据问题列表修复代码。" -ForegroundColor White
    
    # 修复安全问题
    Write-DemoStep "测试 1: 修复安全问题（eval 函数）"
    Invoke-FunctionDemo "fix_issues" "test_data/sample_code.py 中存在安全问题：使用 eval() 函数，应该替换为安全的解析方法"
    
    Start-Sleep -Seconds 2
    
    # 修复性能问题
    Write-DemoStep "测试 2: 修复性能问题（循环优化）"
    Invoke-FunctionDemo "fix_issues" "test_data/sample_code.js 中存在性能问题：应该使用 reduce 方法优化循环"
}

# Demo 4: run_tests
function Demo-RunTests {
    Write-DemoHeader "Demo 4: run_tests - 运行测试"
    
    Write-Host "`n  这个 function 会检测并运行项目的测试。" -ForegroundColor White
    
    # Python 测试
    Write-DemoStep "测试 1: 运行 Python 测试"
    Invoke-FunctionDemo "run_tests" "test_data/test_sample.py"
    
    Start-Sleep -Seconds 2
    
    # JavaScript 测试
    Write-DemoStep "测试 2: 运行 JavaScript 测试"
    Invoke-FunctionDemo "run_tests" "test_data/test_sample.js"
    
    Start-Sleep -Seconds 2
    
    # 整个目录
    Write-DemoStep "测试 3: 运行整个测试目录"
    Invoke-FunctionDemo "run_tests" "test_data/"
}

# Demo 5: 完整调用链
function Demo-CompleteChain {
    Write-DemoHeader "Demo 5: 完整调用链演示"
    
    Write-Host "`n  这个演示展示了一个完整的 workflow：" -ForegroundColor White
    Write-Host "  1. code_review 审查代码" -ForegroundColor White
    Write-Host "  2. 发现问题后自动调用 fix_issues" -ForegroundColor White
    Write-Host "  3. 修复后自动调用 run_tests 验证" -ForegroundColor White
    Write-Host "`n  让我们从 code_review 开始：" -ForegroundColor White
    
    Write-DemoStep "启动完整流程：code_review → fix_issues → run_tests"
    Invoke-FunctionDemo "code_review" "test_data/sample_code.py security"
    
    Write-Host "`n  💡 提示：如果 code_review 发现问题，会自动调用 fix_issues" -ForegroundColor Cyan
    Write-Host "     如果 fix_issues 涉及核心逻辑，会自动调用 run_tests" -ForegroundColor Cyan
}

# 主执行
Write-Host "`n"
Write-Host "╔══════════════════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║                    Function Skill 演示程序                                   ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan

switch ($Demo) {
    "task_orchestrator" {
        Demo-TaskOrchestrator
    }
    "code_review" {
        Demo-CodeReview
    }
    "fix_issues" {
        Demo-FixIssues
    }
    "run_tests" {
        Demo-RunTests
    }
    "demo_chain" {
        Demo-CompleteChain
    }
    "all" {
        Demo-TaskOrchestrator
        Start-Sleep -Seconds 3
        Demo-CodeReview
        Start-Sleep -Seconds 3
        Demo-FixIssues
        Start-Sleep -Seconds 3
        Demo-RunTests
        Start-Sleep -Seconds 3
        Demo-CompleteChain
    }
}

Write-Host "`n"
Write-Host "✅ 演示完成！" -ForegroundColor Green
Write-Host "`n  提示：在实际使用中，这些 function 会在 Claude Code 中自动执行。" -ForegroundColor Gray
Write-Host "  如果执行中断，可以使用 scripts\drive.ps1 继续执行。" -ForegroundColor Gray
