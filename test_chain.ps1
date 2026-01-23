# test_chain.ps1
# 专门用于测试 function 连续调用链的脚本
#
# 用法:
#   .\test_chain.ps1              # 运行完整调用链测试
#   .\test_chain.ps1 -Verbose     # 详细输出

param(
    [switch]$Verbose
)

$ErrorActionPreference = "Continue"

function Write-ChainHeader {
    param([string]$Message)
    Write-Host "`n" -NoNewline
    Write-Host "╔" + ("═" * 78) + "╗" -ForegroundColor Cyan
    Write-Host "║  $Message" -ForegroundColor Cyan
    Write-Host "╚" + ("═" * 78) + "╝" -ForegroundColor Cyan
}

function Write-ChainStep {
    param(
        [int]$Step,
        [int]$Total,
        [string]$FunctionName,
        [string]$Input
    )
    Write-Host "`n[$Step/$Total] " -NoNewline -ForegroundColor Yellow
    Write-Host "$FunctionName" -ForegroundColor Cyan
    Write-Host ("─" * 80) -ForegroundColor Gray
    Write-Host "  输入: $Input" -ForegroundColor Gray
}

Write-ChainHeader "Function 连续调用链测试"

Write-Host "`n这个测试将展示完整的 function 调用链：" -ForegroundColor White
Write-Host "  code_review → fix_issues → run_tests" -ForegroundColor Yellow
Write-Host "`n确保以下文件存在：" -ForegroundColor White
Write-Host "  ✓ test_data/sample_code.py" -ForegroundColor Gray
Write-Host "  ✓ test_data/test_sample.py" -ForegroundColor Gray
Write-Host "  ✓ functions/code_review.json" -ForegroundColor Gray
Write-Host "  ✓ functions/fix_issues.json" -ForegroundColor Gray
Write-Host "  ✓ functions/run_tests.json" -ForegroundColor Gray

# 检查文件
$FilesToCheck = @(
    "test_data/sample_code.py",
    "test_data/test_sample.py",
    "functions/code_review.json",
    "functions/fix_issues.json",
    "functions/run_tests.json"
)

$AllFilesExist = $true
foreach ($file in $FilesToCheck) {
    if (-not (Test-Path $file)) {
        Write-Host "  ✗ $file 不存在" -ForegroundColor Red
        $AllFilesExist = $false
    }
}

if (-not $AllFilesExist) {
    Write-Host "`n❌ 缺少必要文件，请先创建测试数据" -ForegroundColor Red
    exit 1
}

Write-Host "`n✅ 所有文件检查通过" -ForegroundColor Green

# 显示调用链结构
Write-Host "`n调用链结构：" -ForegroundColor Cyan
Write-Host @"
  ┌─────────────────┐
  │  code_review    │  ← 开始：审查代码
  └────────┬────────┘
           │ (发现问题)
           ↓
  ┌─────────────────┐
  │  fix_issues     │  ← 自动调用：修复问题
  └────────┬────────┘
           │ (涉及核心逻辑)
           ↓
  ┌─────────────────┐
  │  run_tests      │  ← 自动调用：验证修复
  └────────┬────────┘
           │ (测试通过)
           ↓
        _return
"@ -ForegroundColor Gray

# 生成测试命令
Write-ChainHeader "测试命令"

$TestCommand = "/fn code_review test_data/sample_code.py security"

Write-Host "`n在 Claude Code 中输入以下命令：" -ForegroundColor Yellow
Write-Host "`n  $TestCommand" -ForegroundColor White -BackgroundColor DarkBlue
Write-Host ""

# 显示预期执行流程
Write-ChainHeader "预期执行流程"

Write-ChainStep 1 3 "code_review" "test_data/sample_code.py security"
Write-Host "  任务: 审查代码安全性" -ForegroundColor Gray
Write-Host "  预期输出:" -ForegroundColor Yellow
Write-Host "    • 发现安全问题（eval、密码明文）" -ForegroundColor White
Write-Host "    • need_fix = true" -ForegroundColor White
Write-Host "    • 🔄 自动调用 → fix_issues" -ForegroundColor Green

Write-ChainStep 2 3 "fix_issues" "[来自 code_review 的问题列表]"
Write-Host "  任务: 修复代码问题" -ForegroundColor Gray
Write-Host "  预期输出:" -ForegroundColor Yellow
Write-Host "    • 修复 eval() 安全问题" -ForegroundColor White
Write-Host "    • 修复密码存储问题" -ForegroundColor White
Write-Host "    • 🔄 自动调用 → run_tests" -ForegroundColor Green

Write-ChainStep 3 3 "run_tests" "test_data/test_sample.py"
Write-Host "  任务: 运行测试验证" -ForegroundColor Gray
Write-Host "  预期输出:" -ForegroundColor Yellow
Write-Host "    • 运行测试文件" -ForegroundColor White
Write-Host "    • 测试结果（通过/失败）" -ForegroundColor White
Write-Host "    • 🔄 调用链完成 → _return" -ForegroundColor Green

# 提供备用测试命令
Write-ChainHeader "备用测试命令"

Write-Host "`n如果上面的命令没有触发完整调用链，尝试以下命令：" -ForegroundColor Yellow

$AlternativeCommands = @(
    @{
        Name = "明确指定需要修复"
        Command = "/fn code_review test_data/sample_code.py security"
        Note = "确保输出中包含 '需要修复' 或 'need_fix = true'"
    },
    @{
        Name = "从修复开始"
        Command = "/fn fix_issues test_data/sample_code.py 中存在安全问题：使用 eval() 函数，需要修复并运行测试验证"
        Note = "直接触发 fix_issues → run_tests"
    },
    @{
        Name = "任务编排器路由"
        Command = "/fn task_orchestrator 请审查 test_data/sample_code.py 的安全性，如果发现问题请修复并运行测试"
        Note = "通过 task_orchestrator 路由到 code_review"
    }
)

foreach ($cmd in $AlternativeCommands) {
    Write-Host "`n  [$($cmd.Name)]" -ForegroundColor Cyan
    Write-Host "    $($cmd.Command)" -ForegroundColor White
    Write-Host "    说明: $($cmd.Note)" -ForegroundColor Gray
}

# 验证检查点
Write-ChainHeader "验证检查点"

Write-Host "`n执行后，检查以下内容：" -ForegroundColor Yellow

$Checkpoints = @(
    @{
        Step = "code_review"
        Checks = @(
            "输出中包含 '发现' 或 '问题'"
            "输出中包含 'need_fix = true' 或 '需要修复'"
            "看到 '🔄 自动调用: fix_issues' 或类似提示"
            "看到 '执行 function: fix_issues'"
        )
    },
    @{
        Step = "fix_issues"
        Checks = @(
            "输出中包含 '修复' 或 '已修复'"
            "输出中包含 '涉及核心逻辑' 或 '需要运行测试'"
            "看到 '🔄 自动调用: run_tests' 或类似提示"
            "看到 '执行 function: run_tests'"
        )
    },
    @{
        Step = "run_tests"
        Checks = @(
            "输出中包含 '测试' 或 'test'"
            "输出中包含测试结果（通过/失败）"
            "看到 '调用链完成' 或 '返回结果'"
        )
    }
)

foreach ($checkpoint in $Checkpoints) {
    Write-Host "`n  [$($checkpoint.Step)]" -ForegroundColor Cyan
    foreach ($check in $checkpoint.Checks) {
        Write-Host "    ☐ $check" -ForegroundColor Gray
    }
}

# 故障排除
Write-ChainHeader "故障排除"

Write-Host @"
如果调用链没有触发：

1. 检查 function 定义文件
   - functions/code_review.json 中的 on_complete 配置
   - functions/fix_issues.json 中的 on_complete 配置
   - functions/run_tests.json 中的 on_complete 配置

2. 确保测试数据包含明显问题
   - test_data/sample_code.py 包含 eval() 函数
   - test_data/sample_code.py 包含密码明文存储

3. 如果执行中断
   - 在 Claude Code 中发送 "继续"
   - 或运行: .\scripts\drive.ps1

4. 查看详细日志
   - 检查每个 function 的输出
   - 确认条件判断是否正确
"@ -ForegroundColor Gray

Write-Host "`n"
Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  准备就绪！现在在 Claude Code 中输入上面的测试命令" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
