<#
.SYNOPSIS
    Automated Test Suite for stack_ops.ps1 and check_chain.ps1

.DESCRIPTION
    Run: powershell -ExecutionPolicy Bypass -File scripts/test_stack_ops.ps1
    
    All test sessions use "_test_" prefix and are cleaned up after tests.
#>

$ErrorActionPreference = "Continue"

# 路径配置
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$StatesDir = Join-Path $ScriptDir "states"
$StackOps = Join-Path $ScriptDir "stack_ops.ps1"
$CheckChain = Join-Path $ScriptDir "check_chain.ps1"

# 测试 session 前缀
$TestPrefix = "_test_ps_"

# 统计
$script:Passed = 0
$script:Failed = 0
$script:Errors = @()

function Run-StackOps {
    param([string]$Session, [string]$Op, [string[]]$ExtraArgs)
    
    # 直接调用脚本（当前已经在 PowerShell 中）
    $scriptArgs = @{
        Session = $Session
        Op = $Op
    }
    
    # 解析额外参数
    foreach ($arg in $ExtraArgs) {
        if ($arg -eq "-Fn") { $nextIsFn = $true; continue }
        if ($nextIsFn) { $scriptArgs["Fn"] = $arg; $nextIsFn = $false; continue }
        if ($arg -eq "-ArgList") { $nextIsArgList = $true; continue }
        if ($nextIsArgList) { $scriptArgs["ArgList"] = $arg; $nextIsArgList = $false; continue }
        if ($arg -eq "-Value") { $nextIsValue = $true; continue }
        if ($nextIsValue) { $scriptArgs["Value"] = $arg; $nextIsValue = $false; continue }
        if ($arg -eq "-VarList") { $nextIsVarList = $true; continue }
        if ($nextIsVarList) { $scriptArgs["VarList"] = $arg; $nextIsVarList = $false; continue }
        if ($arg -eq "-Key") { $nextIsKey = $true; continue }
        if ($nextIsKey) { $scriptArgs["Key"] = $arg; $nextIsKey = $false; continue }
        if ($arg -eq "-Keys") { $nextIsKeys = $true; continue }
        if ($nextIsKeys) { $scriptArgs["Keys"] = $arg; $nextIsKeys = $false; continue }
        if ($arg -eq "-StepIndex") { $nextIsStepIndex = $true; continue }
        if ($nextIsStepIndex) { $scriptArgs["StepIndex"] = [int]$arg; $nextIsStepIndex = $false; continue }
        if ($arg -eq "-Prev") { $nextIsPrev = $true; continue }
        if ($nextIsPrev) { $scriptArgs["Prev"] = $arg; $nextIsPrev = $false; continue }
    }
    
    $output = ""
    $exitCode = 0
    try {
        # Use Start-Process to capture exit code properly, or run in subprocess
        # Write-Host output goes to console, not stdout, so we use process exit code
        $output = & $StackOps @scriptArgs *>&1 | Out-String
        $exitCode = $LASTEXITCODE
        if ($null -eq $exitCode) { $exitCode = 0 }
    } catch {
        $output = $_.Exception.Message
        $exitCode = 1
    }
    
    return @{
        Output = $output
        ExitCode = $exitCode
    }
}

function Load-State {
    param([string]$Session)
    $file = Join-Path $StatesDir "$Session.json"
    if (Test-Path $file) {
        return Get-Content $file -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    return $null
}

function Cleanup-TestSessions {
    if (Test-Path $StatesDir) {
        Get-ChildItem $StatesDir -Filter "$TestPrefix*.json" | Remove-Item -Force -ErrorAction SilentlyContinue
    }
}

function Test-Assert {
    param([string]$Name, [bool]$Condition, [string]$Msg = "")
    
    if ($Condition) {
        $script:Passed++
        Write-Host "  [PASS] $Name" -ForegroundColor Green
    } else {
        $script:Failed++
        $errorMsg = "  [FAIL] $Name"
        if ($Msg) { $errorMsg += ": $Msg" }
        Write-Host $errorMsg -ForegroundColor Red
        $script:Errors += $errorMsg
    }
}

function Test-Section {
    param([string]$Name)
    Write-Host ""
    Write-Host ("=" * 60) -ForegroundColor Cyan
    Write-Host "  $Name" -ForegroundColor Cyan
    Write-Host ("=" * 60) -ForegroundColor Cyan
}

# ============== 测试用例 ==============

function Test-BasicOperations {
    Test-Section "Basic Operations"
    $session = "${TestPrefix}basic"
    
    # init
    $r = Run-StackOps $session "init"
    Test-Assert "init returns 0" ($r.ExitCode -eq 0)
    $state = Load-State $session
    Test-Assert "init creates idle state" ($state.status -eq "idle")
    Test-Assert "init creates empty stack" ($state.stack.Count -eq 0)
    
    # push
    $r = Run-StackOps $session "push" @("-Fn", "route_a", "-ArgList", "n=5,from=main")
    Test-Assert "push returns 0" ($r.ExitCode -eq 0)
    $state = Load-State $session
    Test-Assert "push sets status=running" ($state.status -eq "running")
    Test-Assert "push adds frame" ($state.stack.Count -eq 1)
    Test-Assert "push sets function name" ($state.stack[0].function -eq "route_a")
    
    # peek
    $r = Run-StackOps $session "peek"
    Test-Assert "peek returns 0" ($r.ExitCode -eq 0)
    
    # show
    $r = Run-StackOps $session "show"
    Test-Assert "show returns 0" ($r.ExitCode -eq 0)
    
    # pop
    $r = Run-StackOps $session "pop"
    Test-Assert "pop returns 0" ($r.ExitCode -eq 0)
    $state = Load-State $session
    Test-Assert "pop removes frame" ($state.stack.Count -eq 0)
    Test-Assert "pop sets status=idle" ($state.status -eq "idle")
    
    # clear
    Run-StackOps $session "push" @("-Fn", "test_fn") | Out-Null
    $r = Run-StackOps $session "clear"
    Test-Assert "clear returns 0" ($r.ExitCode -eq 0)
    $state = Load-State $session
    Test-Assert "clear empties stack" ($state.stack.Count -eq 0)
}

function Test-TailCallAndReturn {
    Test-Section "Tail Call and Return"
    $session = "${TestPrefix}tailcall"
    
    Run-StackOps $session "init" | Out-Null
    Run-StackOps $session "push" @("-Fn", "route_a", "-ArgList", "n=3") | Out-Null
    
    # tail_call
    $r = Run-StackOps $session "tail_call" @("-Fn", "route_b", "-ArgList", "n=2")
    Test-Assert "tail_call returns 0" ($r.ExitCode -eq 0)
    $state = Load-State $session
    Test-Assert "tail_call keeps depth=1" ($state.stack.Count -eq 1)
    Test-Assert "tail_call replaces function" ($state.stack[0].function -eq "route_b")
    
    # return with value
    $r = Run-StackOps $session "return" @("-Value", "result_value")
    Test-Assert "return returns 0" ($r.ExitCode -eq 0)
    $state = Load-State $session
    Test-Assert "return pops stack" ($state.stack.Count -eq 0)
    Test-Assert "return sets output" ($state.output -eq "result_value")
    Test-Assert "return sets idle" ($state.status -eq "idle")
}

function Test-StatusOperations {
    Test-Section "Status Operations"
    $session = "${TestPrefix}status"
    
    Run-StackOps $session "init" | Out-Null
    
    # set_status running
    $r = Run-StackOps $session "set_status" @("-Value", "running")
    Test-Assert "set_status running returns 0" ($r.ExitCode -eq 0)
    $state = Load-State $session
    Test-Assert "set_status running works" ($state.status -eq "running")
    
    # set_status error
    $r = Run-StackOps $session "set_status" @("-Value", "error")
    Test-Assert "set_status error returns 0" ($r.ExitCode -eq 0)
    $state = Load-State $session
    Test-Assert "set_status error works" ($state.status -eq "error")
    
    # set_status idle
    $r = Run-StackOps $session "set_status" @("-Value", "idle")
    $state = Load-State $session
    Test-Assert "set_status idle works" ($state.status -eq "idle")
}

function Test-AgentId {
    Test-Section "Controller Agent ID"
    $session = "${TestPrefix}agent"
    
    Run-StackOps $session "init" | Out-Null
    
    # set_agent_id
    $r = Run-StackOps $session "set_agent_id" @("-Value", "abc-123-def-456")
    Test-Assert "set_agent_id returns 0" ($r.ExitCode -eq 0)
    $state = Load-State $session
    Test-Assert "set_agent_id stores value" ($state.controller_agent_id -eq "abc-123-def-456")
    
    # show displays agent_id
    $r = Run-StackOps $session "show"
    Test-Assert "show runs successfully" ($r.ExitCode -eq 0)
    
    # clear removes agent_id
    Run-StackOps $session "clear" | Out-Null
    $state = Load-State $session
    Test-Assert "clear removes agent_id" ($null -eq $state.controller_agent_id)
}

function Test-LastUpdated {
    Test-Section "Last Updated Timestamp"
    $session = "${TestPrefix}timestamp"
    
    Run-StackOps $session "init" | Out-Null
    $state1 = Load-State $session
    Test-Assert "init sets last_updated" ($null -ne $state1.last_updated)
    
    Start-Sleep -Milliseconds 100
    
    Run-StackOps $session "push" @("-Fn", "test_fn") | Out-Null
    $state2 = Load-State $session
    Test-Assert "push updates last_updated" ($state2.last_updated -ne $state1.last_updated)
}

function Test-VariableOperations {
    Test-Section "Variable Operations"
    $session = "${TestPrefix}vars"
    
    Run-StackOps $session "init" | Out-Null
    Run-StackOps $session "push" @("-Fn", "test_fn") | Out-Null
    
    # set_var
    $r = Run-StackOps $session "set_var" @("-VarList", "x=100,name=test")
    Test-Assert "set_var returns 0" ($r.ExitCode -eq 0)
    $state = Load-State $session
    Test-Assert "set_var stores x" ($state.stack[0].vars.x -eq 100)
    Test-Assert "set_var stores name" ($state.stack[0].vars.name -eq "test")
    
    # get_var
    $r = Run-StackOps $session "get_var" @("-Key", "x")
    Test-Assert "get_var runs successfully" ($r.ExitCode -eq 0)
    
    # del_var
    $r = Run-StackOps $session "del_var" @("-Keys", "x")
    Test-Assert "del_var returns 0" ($r.ExitCode -eq 0)
    $state = Load-State $session
    Test-Assert "del_var removes x" ($null -eq $state.stack[0].vars.x)
}

function Test-NestedCalls {
    Test-Section "Nested Calls and `$prev"
    $session = "${TestPrefix}nested"
    
    Run-StackOps $session "init" | Out-Null
    Run-StackOps $session "push" @("-Fn", "parent") | Out-Null
    Run-StackOps $session "push" @("-Fn", "child") | Out-Null
    
    $state = Load-State $session
    Test-Assert "nested push creates depth=2" ($state.stack.Count -eq 2)
    
    # return with value - should set parent's prev
    $r = Run-StackOps $session "return" @("-Value", "child_result")
    $state = Load-State $session
    Test-Assert "return pops to depth=1" ($state.stack.Count -eq 1)
    Test-Assert "return sets parent.prev" ($state.stack[0].prev -eq "child_result")
}

function Test-OutputOperations {
    Test-Section "Output Operations"
    $session = "${TestPrefix}output"
    
    Run-StackOps $session "init" | Out-Null
    
    # set_output
    $r = Run-StackOps $session "set_output" @("-Value", "hello world")
    Test-Assert "set_output returns 0" ($r.ExitCode -eq 0)
    $state = Load-State $session
    Test-Assert "set_output stores value" ($state.output -eq "hello world")
}

function Test-UpdateOperation {
    Test-Section "Update Operation"
    $session = "${TestPrefix}update"
    
    Run-StackOps $session "init" | Out-Null
    Run-StackOps $session "push" @("-Fn", "test_fn") | Out-Null
    
    # update step_index
    $r = Run-StackOps $session "update" @("-StepIndex", "2")
    Test-Assert "update step_index returns 0" ($r.ExitCode -eq 0)
    $state = Load-State $session
    Test-Assert "update sets step_index" ($state.stack[0].step_index -eq 2)
    
    # update prev
    $r = Run-StackOps $session "update" @("-Prev", "previous_value")
    Test-Assert "update prev returns 0" ($r.ExitCode -eq 0)
    $state = Load-State $session
    Test-Assert "update sets prev" ($state.stack[0].prev -eq "previous_value")
}

function Run-CheckChain {
    param([string]$Session)
    
    $output = ""
    $exitCode = 0
    
    try {
        # 使用 cmd /c 提供空 stdin，通过 -TestSession 参数传递 session
        # 2>&1 在 cmd 层面重定向 stderr 到 stdout
        $result = cmd /c "echo. | powershell -ExecutionPolicy Bypass -File `"$CheckChain`" -TestSession `"$Session`" 2>&1"
        $exitCode = $LASTEXITCODE
        $output = $result | Out-String
    } catch {
        $output = $_.Exception.Message
        $exitCode = 1
    }
    
    return @{
        Output = $output
        ExitCode = $exitCode
    }
}

function Test-CheckChain {
    Test-Section "Check Chain (Stop Hook)"
    $session = "${TestPrefix}hook"
    
    # 空栈应允许停止
    Run-StackOps $session "init" | Out-Null
    $r = Run-CheckChain $session
    Test-Assert "empty stack allows stop (exit 0)" ($r.ExitCode -eq 0)
    Test-Assert "empty stack outputs [ok]" ($r.Output -match "\[ok\]")
    
    # 非空栈应阻止停止
    Run-StackOps $session "push" @("-Fn", "route_a", "-ArgList", "n=3") | Out-Null
    $r = Run-CheckChain $session
    Test-Assert "non-empty stack blocks stop (exit 2)" ($r.ExitCode -eq 2)
    Test-Assert "non-empty outputs STOP-HOOK" ($r.Output -match "STOP-HOOK")
    Test-Assert "non-empty shows stack depth" ($r.Output -match "Stack depth:")
    
    # 非空栈显示 continue 指令
    Test-Assert "shows operation=continue" ($r.Output -match "operation=continue")
    Test-Assert "shows fn-controller prompt" ($r.Output -match "fn-controller")
}

function Test-CallAlias {
    Test-Section "Call Alias"
    $session = "${TestPrefix}call"
    
    Run-StackOps $session "init" | Out-Null
    $r = Run-StackOps $session "call" @("-Fn", "route_a", "-ArgList", "n=1")
    Test-Assert "call returns 0" ($r.ExitCode -eq 0)
    $state = Load-State $session
    Test-Assert "call adds frame" ($state.stack.Count -eq 1)
    Test-Assert "call sets function" ($state.stack[0].function -eq "route_a")
}

function Test-SequenceStepIndex {
    Test-Section "Sequence Step Index Continuity"
    $session = "${TestPrefix}sequence"
    
    # 初始化
    Run-StackOps $session "clear" | Out-Null
    Run-StackOps $session "push" @("-Fn", "test/sequence_func") | Out-Null
    
    # 首次更新: 设置 step_index=1 (有效 - 首次更新)
    $r = Run-StackOps $session "update" @("-StepIndex", "1")
    Test-Assert "step_index=1 (first update) succeeds" ($r.ExitCode -eq 0)
    $state = Load-State $session
    Test-Assert "step_index is set to 1" ($state.stack[0].step_index -eq 1)
    
    # 连续更新: step_index=2 (有效 - 连续递增)
    $r = Run-StackOps $session "update" @("-StepIndex", "2")
    Test-Assert "step_index=2 (continuous) succeeds" ($r.ExitCode -eq 0)
    $state = Load-State $session
    Test-Assert "step_index is set to 2" ($state.stack[0].step_index -eq 2)
    
    # 跳步更新: step_index=4 (应该失败)
    $r = Run-StackOps $session "update" @("-StepIndex", "4")
    Test-Assert "step_index=4 (skip) fails" ($r.ExitCode -ne 0)
    Test-Assert "skip error message mentions step_index" ($r.Output -match "step_index" -or $r.Output -match "\[ERROR\]")
    $state = Load-State $session
    Test-Assert "step_index unchanged after skip failure" ($state.stack[0].step_index -eq 2)
    
    # 清理
    Run-StackOps $session "clear" | Out-Null
}

function Test-SequenceForceStepIndex {
    Test-Section "Sequence Force Step Index"
    $session = "${TestPrefix}seqforce"
    
    # 初始化
    Run-StackOps $session "clear" | Out-Null
    Run-StackOps $session "push" @("-Fn", "test/sequence_func") | Out-Null
    Run-StackOps $session "update" @("-StepIndex", "1") | Out-Null
    Run-StackOps $session "update" @("-StepIndex", "2") | Out-Null
    
    # 使用 -ForceStepIndex 跳过验证 (应该成功)
    # 直接调用脚本，添加 -ForceStepIndex 开关
    $scriptArgs = @{
        Session = $session
        Op = "update"
        StepIndex = 5
        ForceStepIndex = $true
    }
    $output = ""
    try {
        $output = & $StackOps @scriptArgs 2>&1 | Out-String
        $exitCode = if ($output -match "\[ERROR\]") { 1 } else { 0 }
    } catch {
        $output = $_.Exception.Message
        $exitCode = 1
    }
    Test-Assert "force step_index=5 succeeds" ($exitCode -eq 0)
    $state = Load-State $session
    Test-Assert "step_index is set to 5 with force" ($state.stack[0].step_index -eq 5)
    
    # 清理
    Run-StackOps $session "clear" | Out-Null
}

function Test-SequenceSimulation {
    Test-Section "4-Step Sequence Simulation"
    $session = "${TestPrefix}seqsim"
    
    # 清理并初始化
    Run-StackOps $session "clear" | Out-Null
    
    # 模拟: push 主函数 (带 sequence)
    Run-StackOps $session "push" @("-Fn", "tests/test_sequence_4steps", "-ArgList", "input=hello") | Out-Null
    
    # Step 0: 执行 step[0] (call seq_step1)
    Run-StackOps $session "update" @("-StepIndex", "1") | Out-Null  # 更新为下一步
    Run-StackOps $session "push" @("-Fn", "tests/seq_step1", "-ArgList", "data=hello") | Out-Null
    
    # seq_step1 返回
    Run-StackOps $session "return" @("-Value", "step1_hello") | Out-Null
    
    # 验证父帧有 prev
    $state = Load-State $session
    Test-Assert "step 0: parent has prev" ($state.stack[0].prev -eq "step1_hello")
    Test-Assert "step 0: step_index is 1" ($state.stack[0].step_index -eq 1)
    
    # Step 1: 执行 step[1] (call seq_step2)
    Run-StackOps $session "update" @("-StepIndex", "2") | Out-Null
    Run-StackOps $session "push" @("-Fn", "tests/seq_step2", "-ArgList", "data=step1_hello") | Out-Null
    
    # seq_step2 返回
    Run-StackOps $session "return" @("-Value", "step1_hello_step2") | Out-Null
    
    $state = Load-State $session
    Test-Assert "step 1: prev updated" ($state.stack[0].prev -eq "step1_hello_step2")
    Test-Assert "step 1: step_index is 2" ($state.stack[0].step_index -eq 2)
    
    # Step 2: 执行 step[2] (call seq_step3)
    Run-StackOps $session "update" @("-StepIndex", "3") | Out-Null
    Run-StackOps $session "push" @("-Fn", "tests/seq_step3", "-ArgList", "data=step1_hello_step2") | Out-Null
    
    # seq_step3 返回
    Run-StackOps $session "return" @("-Value", "COMPLETED_step1_hello_step2") | Out-Null
    
    $state = Load-State $session
    Test-Assert "step 2: prev updated" ($state.stack[0].prev -eq "COMPLETED_step1_hello_step2")
    Test-Assert "step 2: step_index is 3" ($state.stack[0].step_index -eq 3)
    
    # Step 3: 执行 step[3] (tail_call seq_step4)
    Run-StackOps $session "tail_call" @("-Fn", "tests/seq_step4", "-ArgList", "data=COMPLETED_step1_hello_step2") | Out-Null
    
    $state = Load-State $session
    Test-Assert "step 3: tail_called to seq_step4" ($state.stack[0].function -eq "tests/seq_step4")
    
    # seq_step4 返回 (最终步骤)
    Run-StackOps $session "return" @("-Value", "FINAL_COMPLETED_step1_hello_step2") | Out-Null
    
    $state = Load-State $session
    Test-Assert "sequence complete: stack empty" ($state.stack.Count -eq 0)
    Test-Assert "sequence complete: status idle" ($state.status -eq "idle")
    
    # 清理
    Run-StackOps $session "clear" | Out-Null
}

function Test-StepSkipDetection {
    Test-Section "Step Skip Detection"
    $session = "${TestPrefix}skipdetect"
    
    # 清理并初始化
    Run-StackOps $session "clear" | Out-Null
    Run-StackOps $session "push" @("-Fn", "tests/test_sequence", "-ArgList", "input=test") | Out-Null
    Run-StackOps $session "update" @("-StepIndex", "1") | Out-Null  # step 0 完成
    
    # 尝试跳到 step_index=3 (应该失败)
    $r = Run-StackOps $session "update" @("-StepIndex", "3")
    Test-Assert "skip 1->3 rejected" ($r.ExitCode -ne 0)
    
    # 正确递增到 2 应该成功
    $r = Run-StackOps $session "update" @("-StepIndex", "2")
    Test-Assert "proper increment 1->2 succeeds" ($r.ExitCode -eq 0)
    
    $state = Load-State $session
    Test-Assert "step_index is now 2" ($state.stack[0].step_index -eq 2)
    
    # 清理
    Run-StackOps $session "clear" | Out-Null
}

function Test-GetNextAction {
    Test-Section "Get Next Action"
    $session = "${TestPrefix}nextaction"
    
    # 空栈应返回 complete
    Run-StackOps $session "init" | Out-Null
    $r = Run-StackOps $session "get_next_action"
    Test-Assert "get_next_action returns 0 (empty)" ($r.ExitCode -eq 0)
    Test-Assert "get_next_action outputs JSON" ($r.Output -match "\{")
    Test-Assert "empty stack returns next_action=complete" ($r.Output -match '"next_action"\s*:\s*"complete"')
    Test-Assert "empty stack has depth=0" ($r.Output -match '"depth"\s*:\s*0')
    
    # 非空栈应返回 continue
    Run-StackOps $session "push" @("-Fn", "route_a", "-ArgList", "n=5,from=main") | Out-Null
    $r = Run-StackOps $session "get_next_action"
    Test-Assert "get_next_action returns 0 (non-empty)" ($r.ExitCode -eq 0)
    Test-Assert "non-empty returns next_action=continue" ($r.Output -match '"next_action"\s*:\s*"continue"')
    Test-Assert "non-empty has depth=1" ($r.Output -match '"depth"\s*:\s*1')
    Test-Assert "non-empty has top_frame" ($r.Output -match '"top_frame"')
    Test-Assert "top_frame has function" ($r.Output -match '"function"\s*:\s*"route_a"')
    Test-Assert "top_frame has args" ($r.Output -match '"args"')
    
    # 有 prev 时应显示 has_prev
    Run-StackOps $session "push" @("-Fn", "child") | Out-Null
    Run-StackOps $session "return" @("-Value", "child_result") | Out-Null
    $r = Run-StackOps $session "get_next_action"
    Test-Assert "has_prev shows when prev exists" ($r.Output -match '"has_prev"\s*:\s*true')
    
    # 栈空后应返回 complete
    Run-StackOps $session "return" | Out-Null
    $r = Run-StackOps $session "get_next_action"
    Test-Assert "after return empty returns complete" ($r.Output -match '"next_action"\s*:\s*"complete"')
}

function Test-ErrorHandling {
    Test-Section "Error Handling"
    $session = "${TestPrefix}errors"
    
    Run-StackOps $session "init" | Out-Null
    
    # 验证空栈操作：状态应该保持不变（stack 仍为空）
    $stateBefore = Load-State $session
    
    # pop 空栈
    $r = Run-StackOps $session "pop"
    $stateAfter = Load-State $session
    Test-Assert "pop empty stack keeps state unchanged" ($stateAfter.stack.Count -eq $stateBefore.stack.Count)
    
    # tail_call 空栈
    $r = Run-StackOps $session "tail_call" @("-Fn", "route_a")
    $stateAfter = Load-State $session
    Test-Assert "tail_call empty stack keeps state unchanged" ($stateAfter.stack.Count -eq 0)
    
    # return 空栈
    $r = Run-StackOps $session "return"
    $stateAfter = Load-State $session
    Test-Assert "return empty stack keeps state unchanged" ($stateAfter.stack.Count -eq 0)
    
    # 缺少参数 - push 不会改变状态
    $r = Run-StackOps $session "push"
    $stateAfter = Load-State $session
    Test-Assert "push without fqn keeps state unchanged" ($stateAfter.stack.Count -eq 0)
}

# ============== 主入口 ==============

Write-Host ""
Write-Host ("=" * 60) -ForegroundColor Yellow
Write-Host "  Stack Operations Test Suite (PowerShell)" -ForegroundColor Yellow
Write-Host "  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Yellow
Write-Host ("=" * 60) -ForegroundColor Yellow

# 确保 states 目录存在
if (-not (Test-Path $StatesDir)) {
    New-Item -ItemType Directory -Path $StatesDir -Force | Out-Null
}

# 清理之前的测试残留
Cleanup-TestSessions

try {
    # 运行所有测试
    Test-BasicOperations
    Test-TailCallAndReturn
    Test-NestedCalls
    Test-StatusOperations
    Test-AgentId
    Test-LastUpdated
    Test-OutputOperations
    Test-VariableOperations
    Test-UpdateOperation
    Test-CheckChain
    Test-GetNextAction
    Test-ErrorHandling
    Test-CallAlias
    
    # Sequence step tests (防止跳步 bug)
    Test-SequenceStepIndex
    Test-SequenceForceStepIndex
    Test-SequenceSimulation
    Test-StepSkipDetection
}
finally {
    # 清理测试 session
    Write-Host ""
    Write-Host ("=" * 60) -ForegroundColor Cyan
    Write-Host "  Cleanup" -ForegroundColor Cyan
    Write-Host ("=" * 60) -ForegroundColor Cyan
    Cleanup-TestSessions
    Write-Host "  [PASS] Test sessions cleaned up" -ForegroundColor Green
}

# 汇总
Write-Host ""
Write-Host ("=" * 60) -ForegroundColor Yellow
if ($script:Failed -eq 0) {
    Write-Host "  Results: $($script:Passed) passed, $($script:Failed) failed" -ForegroundColor Green
} else {
    Write-Host "  Results: $($script:Passed) passed, $($script:Failed) failed" -ForegroundColor Red
}
Write-Host ("=" * 60) -ForegroundColor Yellow

if ($script:Errors.Count -gt 0) {
    Write-Host ""
    Write-Host "Failed tests:" -ForegroundColor Red
    foreach ($e in $script:Errors) {
        Write-Host $e -ForegroundColor Red
    }
}

exit $(if ($script:Failed -eq 0) { 0 } else { 1 })
