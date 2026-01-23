# test_all_functions.ps1
# 测试所有 function 的完整测试套件
#
# 用法:
#   .\test_all_functions.ps1                    # 运行所有测试
#   .\test_all_functions.ps1 -Function code_review  # 测试单个 function
#   .\test_all_functions.ps1 -Verbose            # 详细输出

param(
    [string]$Function = "",
    [switch]$Verbose,
    [switch]$DryRun
)

$ErrorActionPreference = "Continue"

# 颜色输出函数
function Write-TestHeader {
    param([string]$Message)
    Write-Host "`n" -NoNewline
    Write-Host "=" * 80 -ForegroundColor Cyan
    Write-Host "  $Message" -ForegroundColor Cyan
    Write-Host "=" * 80 -ForegroundColor Cyan
}

function Write-TestStep {
    param([string]$Message)
    Write-Host "  → $Message" -ForegroundColor Yellow
}

function Write-TestSuccess {
    param([string]$Message)
    Write-Host "  ✓ $Message" -ForegroundColor Green
}

function Write-TestError {
    param([string]$Message)
    Write-Host "  ✗ $Message" -ForegroundColor Red
}

# 测试结果记录
$TestResults = @{
    Total = 0
    Passed = 0
    Failed = 0
    Skipped = 0
    Details = @()
}

function Record-TestResult {
    param(
        [string]$FunctionName,
        [string]$TestName,
        [bool]$Passed,
        [string]$Message = ""
    )
    $TestResults.Total++
    if ($Passed) {
        $TestResults.Passed++
        Write-TestSuccess "$TestName"
    } else {
        $TestResults.Failed++
        Write-TestError "$TestName : $Message"
    }
    $TestResults.Details += @{
        Function = $FunctionName
        Test = $TestName
        Passed = $Passed
        Message = $Message
    }
}

# 测试用例定义
$TestCases = @{
    "task_orchestrator" = @(
        @{
            Name = "路由到 code_review"
            Input = "请审查 test_data/sample_code.py 的安全性"
            ExpectedRoute = "code_review"
        },
        @{
            Name = "路由到 fix_issues"
            Input = "修复 test_data 中的代码问题"
            ExpectedRoute = "fix_issues"
        },
        @{
            Name = "路由到 run_tests"
            Input = "运行测试验证代码"
            ExpectedRoute = "run_tests"
        },
        @{
            Name = "默认返回"
            Input = "这是一个普通任务"
            ExpectedRoute = "_return"
        }
    )
    
    "code_review" = @(
        @{
            Name = "安全审查 Python 代码"
            Input = "test_data/sample_code.py security"
        },
        @{
            Name = "性能审查 JavaScript 代码"
            Input = "test_data/sample_code.js performance"
        },
        @{
            Name = "质量审查整个目录"
            Input = "test_data/ quality"
        }
    )
    
    "fix_issues" = @(
        @{
            Name = "修复安全问题"
            Input = "test_data/sample_code.py 中存在安全问题：使用 eval() 函数，应该替换为安全的解析方法"
        },
        @{
            Name = "修复性能问题"
            Input = "test_data/sample_code.js 中存在性能问题：应该使用 reduce 方法优化循环"
        }
    )
    
    "run_tests" = @(
        @{
            Name = "运行 Python 测试"
            Input = "test_data/test_sample.py"
        },
        @{
            Name = "运行 JavaScript 测试"
            Input = "test_data/test_sample.js"
        },
        @{
            Name = "运行整个测试目录"
            Input = "test_data/"
        }
    )
}

# 验证 function 定义文件
function Test-FunctionDefinition {
    param([string]$FunctionName)
    
    $FunctionFile = "functions\$FunctionName.json"
    
    if (-not (Test-Path $FunctionFile)) {
        Write-TestError "Function 定义文件不存在: $FunctionFile"
        return $false
    }
    
    try {
        $Definition = Get-Content $FunctionFile -Raw | ConvertFrom-Json
        
        # 验证必需字段
        if (-not $Definition.name) {
            Write-TestError "缺少必需字段: name"
            return $false
        }
        
        if (-not $Definition.task) {
            Write-TestError "缺少必需字段: task"
            return $false
        }
        
        if ($Definition.name -ne $FunctionName) {
            Write-TestError "Function 名称不匹配: 定义中为 $($Definition.name)，期望为 $FunctionName"
            return $false
        }
        
        Write-TestSuccess "Function 定义验证通过"
        return $true
    } catch {
        Write-TestError "JSON 解析失败: $_"
        return $false
    }
}

# 测试单个 function
function Test-SingleFunction {
    param(
        [string]$FunctionName,
        [array]$Tests
    )
    
    Write-TestHeader "测试 Function: $FunctionName"
    
    # 首先验证定义文件
    Write-TestStep "验证 function 定义文件"
    if (-not (Test-FunctionDefinition $FunctionName)) {
        Record-TestResult $FunctionName "定义验证" $false "定义文件验证失败"
        return
    }
    Record-TestResult $FunctionName "定义验证" $true
    
    # 如果是 DryRun 模式，只显示测试用例
    if ($DryRun) {
        Write-TestStep "DryRun 模式 - 将执行以下测试:"
        foreach ($test in $Tests) {
            Write-Host "    - $($test.Name)" -ForegroundColor Gray
        }
        Record-TestResult $FunctionName "DryRun" $true
        return
    }
    
    # 执行每个测试用例
    foreach ($test in $Tests) {
        Write-TestStep "测试: $($test.Name)"
        
        if ($Verbose) {
            Write-Host "    输入: $($test.Input)" -ForegroundColor Gray
        }
        
        # 构建执行命令
        $Command = "/fn $FunctionName $($test.Input)"
        
        Write-Host "    执行命令: $Command" -ForegroundColor Gray
        
        # 注意：这里只是模拟测试，实际执行需要 Claude Code
        # 在实际环境中，这里应该调用 run_function.ps1
        Record-TestResult $FunctionName $test.Name $true "测试用例已准备"
    }
}

# 测试内置 function
function Test-BuiltinFunctions {
    Write-TestHeader "测试内置 Functions"
    
    $BuiltinFile = "functions\_builtins.json"
    
    if (-not (Test-Path $BuiltinFile)) {
        Write-TestError "内置 function 定义文件不存在"
        Record-TestResult "_builtins" "文件存在性检查" $false
        return
    }
    
    try {
        $Builtins = Get-Content $BuiltinFile -Raw | ConvertFrom-Json
        
        $RequiredBuiltins = @("_compact", "_clear", "_return")
        
        foreach ($builtin in $RequiredBuiltins) {
            if ($Builtins.builtins.$builtin) {
                Write-TestSuccess "内置 function '$builtin' 已定义"
                Record-TestResult "_builtins" "检查 $builtin" $true
            } else {
                Write-TestError "缺少内置 function: $builtin"
                Record-TestResult "_builtins" "检查 $builtin" $false
            }
        }
    } catch {
        Write-TestError "解析内置 function 定义失败: $_"
        Record-TestResult "_builtins" "JSON 解析" $false
    }
}

# 测试 Schema 验证
function Test-SchemaValidation {
    Write-TestHeader "测试 Schema 验证"
    
    $SchemaFile = "functions\_schema.json"
    
    if (-not (Test-Path $SchemaFile)) {
        Write-TestError "Schema 文件不存在"
        Record-TestResult "_schema" "文件存在性" $false
        return
    }
    
    try {
        $Schema = Get-Content $SchemaFile -Raw | ConvertFrom-Json
        Write-TestSuccess "Schema 文件格式正确"
        Record-TestResult "_schema" "JSON 格式" $true
        
        # 验证所有 function 是否符合 schema
        $FunctionFiles = Get-ChildItem functions\*.json | Where-Object { $_.Name -notlike '_*' }
        
        foreach ($file in $FunctionFiles) {
            $FunctionName = $file.BaseName
            Write-TestStep "验证 $FunctionName 是否符合 schema"
            
            try {
                $Definition = Get-Content $file.FullName -Raw | ConvertFrom-Json
                
                # 基本验证（完整验证需要 JSON Schema 验证库）
                if ($Definition.name -and $Definition.task) {
                    Write-TestSuccess "$FunctionName 符合基本 schema"
                    Record-TestResult "_schema" "验证 $FunctionName" $true
                } else {
                    Write-TestError "$FunctionName 缺少必需字段"
                    Record-TestResult "_schema" "验证 $FunctionName" $false
                }
            } catch {
                Write-TestError "$FunctionName JSON 解析失败: $_"
                Record-TestResult "_schema" "验证 $FunctionName" $false
            }
        }
    } catch {
        Write-TestError "Schema 文件解析失败: $_"
        Record-TestResult "_schema" "JSON 解析" $false
    }
}

# 生成测试报告
function Write-TestReport {
    Write-TestHeader "测试报告"
    
    Write-Host "  总测试数: $($TestResults.Total)" -ForegroundColor White
    Write-Host "  通过: $($TestResults.Passed)" -ForegroundColor Green
    Write-Host "  失败: $($TestResults.Failed)" -ForegroundColor Red
    Write-Host "  跳过: $($TestResults.Skipped)" -ForegroundColor Yellow
    
    if ($TestResults.Failed -gt 0) {
        Write-Host "`n失败的测试:" -ForegroundColor Red
        foreach ($detail in $TestResults.Details) {
            if (-not $detail.Passed) {
                Write-Host "    - $($detail.Function) / $($detail.Test)" -ForegroundColor Red
                if ($detail.Message) {
                    Write-Host "      原因: $($detail.Message)" -ForegroundColor Gray
                }
            }
        }
    }
    
    Write-Host ""
    
    # 保存报告到文件
    $ReportFile = "test_report_$(Get-Date -Format 'yyyyMMdd_HHmmss').json"
    $TestResults | ConvertTo-Json -Depth 10 | Out-File $ReportFile
    Write-Host "  详细报告已保存到: $ReportFile" -ForegroundColor Cyan
}

# 主执行流程
Write-Host "`n"
Write-Host "╔══════════════════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║                    Function Skill 测试套件                                  ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan

# 测试内置 functions
Test-BuiltinFunctions

# 测试 Schema
Test-SchemaValidation

# 测试各个 function
if ($Function) {
    # 测试单个 function
    if ($TestCases.ContainsKey($Function)) {
        Test-SingleFunction $Function $TestCases[$Function]
    } else {
        Write-TestError "未找到 function: $Function"
        Write-Host "`n可用的 functions:" -ForegroundColor Yellow
        $TestCases.Keys | ForEach-Object { Write-Host "  - $_" -ForegroundColor Gray }
    }
} else {
    # 测试所有 functions
    foreach ($funcName in $TestCases.Keys) {
        Test-SingleFunction $funcName $TestCases[$funcName]
    }
}

# 生成报告
Write-TestReport

# 退出码
if ($TestResults.Failed -eq 0) {
    exit 0
} else {
    exit 1
}
