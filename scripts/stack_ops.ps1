<#
.SYNOPSIS
    Stack Operations Tool - Reliable stack operations with diff feedback

.DESCRIPTION
================================================================================
                              OPERATIONS
================================================================================
  Operation     Arguments                              Description
--------------------------------------------------------------------------------
  push          <fqn> [-ArgList k=v,...]               Push new frame (alias: call)
  pop           [-Output <value>]                      Pop top frame
  tail_call     <fqn> [-ArgList k=v,...]               Tail call (pop+push, depth unchanged)
  return        [-Value <v>]                           Return (pop + set prev + output)
  update        [-StepIndex n] [-Prev v] [-VarList k=v] Update top frame properties
  peek                                                 View top frame
  show                                                 Show full state
  init                                                 Initialize/reset state
  clear                                                Clear stack and output
  set_status    idle|running                           Set status
  set_output    <value>                                Set session output
  set_var       [-VarList k=v,...]                     Batch set temp variables
  get_var       [-Key <key>]                           Read variable (args/prev/vars)
  del_var       [-Keys k1,k2,...]                      Batch delete temp variables
================================================================================

.EXAMPLE
    .\stack_ops.ps1 -Session abc -Op push -Fn route_a -ArgList "n=5,from=main"
    .\stack_ops.ps1 -Session abc -Op tail_call -Fn route_b -ArgList "n=4"
    .\stack_ops.ps1 -Session abc -Op return -Value "completed"
    .\stack_ops.ps1 -Session abc -Op set_var -VarList "x=1,y=2,name=test"
    .\stack_ops.ps1 -Session abc -Op get_var -Key prev
    .\stack_ops.ps1 -Session abc -Op del_var -Keys "x,y"
    .\stack_ops.ps1 -Session abc -Op show
#>

param(
    [Parameter(Position=0)]
    [string]$Session,
    
    [Parameter(Position=1)]
    [ValidateSet("init","push","call","pop","peek","update","set_status","set_output","clear","show","tail_call","return","set_var","get_var","del_var")]
    [string]$Op,
    
    [Parameter(Position=2)]
    [string]$Fn,           # 函数名 (push/tail_call)
    
    [int]$StepIndex = -1,  # step_index (push/update)
    
    [string]$Output,       # output (pop/update)
    
    [string]$Value,        # 通用值 (set_status/set_output/return)
    
    [string]$Status,       # 状态 (set_status)
    
    [string]$ArgList,      # 参数列表: "n=5,from=main" 格式
    
    [string]$Prev,         # prev 值 (update)
    
    [string]$VarList,      # 变量列表: "k1=v1,k2=v2" 格式 (update/set_var)
    
    [string]$Key,          # 变量键名 (get_var)
    
    [string]$Keys,         # 变量键名列表: "k1,k2,k3" 格式 (del_var)
    
    [switch]$Help          # 显示帮助
)

$ErrorActionPreference = "Stop"

# ============== Help Function ==============

function Show-Help {
    $helpText = @"
================================================================================
                     Stack Operations Tool (PowerShell)
================================================================================
  Operation     Arguments                              Description
--------------------------------------------------------------------------------
  push          <fqn> [-ArgList k=v,...]               Push new frame (alias: call)
  pop           [-Output <value>]                      Pop top frame
  tail_call     <fqn> [-ArgList k=v,...]               Tail call (pop+push, depth unchanged)
  return        [-Value <v>]                           Return (pop + set prev + output)
  update        [-StepIndex n] [-Prev v] [-VarList k=v] Update top frame properties
  peek                                                 View top frame
  show                                                 Show full state
  init                                                 Initialize/reset state
  clear                                                Clear stack and output
  set_status    idle|running                           Set status
  set_output    <value>                                Set session output
  set_var       [-VarList k=v,...]                     Batch set temp variables
  get_var       [-Key <key>]                           Read variable (args/prev/vars)
  del_var       [-Keys k1,k2,...]                      Batch delete temp variables
================================================================================

Usage:
    .\stack_ops.ps1 -Session <id> -Op <operation> [options]
    .\stack_ops.ps1 -Help

Examples:
    .\stack_ops.ps1 -Session abc -Op push -Fn route_a -ArgList "n=5,from=main"
    .\stack_ops.ps1 -Session abc -Op tail_call -Fn route_b -ArgList "n=4"
    .\stack_ops.ps1 -Session abc -Op return -Value "completed"
    .\stack_ops.ps1 -Session abc -Op show

Output:
    BEFORE/AFTER summary + detailed DIFF for reviewing operation results

Available operations: init, push, call, pop, peek, update, set_status, set_output, clear, show, tail_call, return, set_var, get_var, del_var
"@
    Write-Host $helpText
}

# 无参数或 -Help 时显示帮助
if ($Help -or (-not $Session -and -not $Op)) {
    Show-Help
    exit 0
}

# 检查必须参数
if (-not $Session) {
    Write-Host "[ERROR] Missing required parameter: -Session"
    Write-Host "Run with -Help to see usage."
    exit 1
}

if (-not $Op) {
    Write-Host "[ERROR] Missing required parameter: -Op"
    Write-Host "Run with -Help to see usage."
    exit 1
}

# 解析 "n=5,from=main" 格式的参数列表
function Parse-ArgList {
    param([string]$List)
    $result = @{}
    
    if (-not $List) { return $result }
    
    foreach ($item in $List.Split(",")) {
        $item = $item.Trim()
        if ($item -match "^([^=]+)=(.*)$") {
            $key = $Matches[1]
            $val = $Matches[2]
            
            # 尝试转换类型
            if ($val -eq "true") { $result[$key] = $true }
            elseif ($val -eq "false") { $result[$key] = $false }
            elseif ($val -match "^-?\d+$") { $result[$key] = [int]$val }
            elseif ($val -match "^-?\d+\.\d+$") { $result[$key] = [double]$val }
            else { $result[$key] = $val }
        }
    }
    
    return $result
}

# 解析参数列表
$Arg = Parse-ArgList $ArgList

# 路径配置
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$StatesDir = Join-Path $ScriptDir "states"

# 确保目录存在
if (-not (Test-Path $StatesDir)) {
    New-Item -ItemType Directory -Path $StatesDir -Force | Out-Null
}

function Get-StateFile {
    param([string]$SessionId)
    return Join-Path $StatesDir "$SessionId.json"
}

function Load-State {
    param([string]$SessionId, [bool]$MustExist = $false)
    $file = Get-StateFile $SessionId
    if (Test-Path $file) {
        try {
            return Get-Content $file -Raw | ConvertFrom-Json
        } catch {
            return @{ status = "idle"; stack = @(); output = $null }
        }
    }
    if ($MustExist) {
        Write-Host ""
        Write-Host "[ERROR] Session file not found: $file"
        Write-Host "Possible causes:"
        Write-Host "  1. Session ID typo (check your `$SID variable)"
        Write-Host "  2. Session not initialized (run push first)"
        Write-Host "  3. Wrong terminal session"
        Write-Host ""
        Write-Host "Available sessions:"
        $sessions = Get-ChildItem $StatesDir -Filter "*.json" -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne ".hook_debug.log" }
        if ($sessions) {
            $sessions | ForEach-Object { Write-Host "  - $($_.BaseName)" }
        } else {
            Write-Host "  (none)"
        }
        exit 1
    }
    return @{ status = "idle"; stack = @(); output = $null }
}

function Save-State {
    param([string]$SessionId, [object]$State)
    $file = Get-StateFile $SessionId
    
    # Ensure depth consistency before save
    $stackLen = if ($State.stack) { @($State.stack).Count } else { 0 }
    
    # Atomic write
    $State | ConvertTo-Json -Depth 10 | Set-Content $file -Encoding UTF8
    
    # Read-back verification
    try {
        $verified = Get-Content $file -Raw -Encoding UTF8 | ConvertFrom-Json
        $verifiedLen = if ($verified.stack) { @($verified.stack).Count } else { 0 }
        if ($verifiedLen -ne $stackLen) {
            throw "Stack length mismatch after save: expected $stackLen, got $verifiedLen"
        }
    } catch {
        Write-Host "[WARN] State verification failed: $_"
    }
}

function Clone-State {
    param([object]$State)
    return $State | ConvertTo-Json -Depth 10 | ConvertFrom-Json
}

function Get-StackDepth {
    param([object]$Stack)
    if (-not $Stack) { return 0 }
    $count = 0
    foreach ($item in $Stack) {
        if ($item -and $item.function) { $count++ }
    }
    return $count
}

function Get-StackTop {
    param([object]$Stack)
    if (-not $Stack) { return $null }
    $lastValid = $null
    foreach ($item in $Stack) {
        if ($item -and $item.function) { $lastValid = $item }
    }
    return $lastValid
}

function Format-StateSummary {
    param([object]$State)
    $status = if ($State.status) { $State.status } else { "idle" }
    $depth = Get-StackDepth $State.stack
    
    $parts = @("status=$status", "depth=$depth")
    
    if ($depth -gt 0) {
        $topFrame = Get-StackTop $State.stack
        if ($topFrame) {
            $top = $topFrame.function
            if ($top -and $top.Length -gt 30) { $top = "..." + $top.Substring($top.Length - 27) }
            if ($top) { $parts += "top=$top" }
        }
    }
    
    if ($State.output) { $parts += "[has_output]" }
    
    return $parts -join " | "
}

function Format-ArgsBrief {
    param([object]$Args)
    if (-not $Args) { return "" }
    
    $items = @()
    
    # 处理 hashtable
    if ($Args -is [hashtable]) {
        foreach ($key in $Args.Keys) {
            $items += "$key=$($Args[$key])"
        }
    }
    # 处理 PSObject (从 JSON 反序列化)
    elseif ($Args.PSObject.Properties) {
        foreach ($prop in $Args.PSObject.Properties) {
            $items += "$($prop.Name)=$($prop.Value)"
        }
    }
    
    if ($items.Count -eq 0) { return "" }
    
    $brief = $items -join ", "
    if ($brief.Length -gt 40) { $brief = $brief.Substring(0, 37) + "..." }
    return " ($brief)"
}

function Compute-Diff {
    param([object]$Before, [object]$After)
    $diff = @()
    
    # 状态变化
    $bStatus = if ($Before.status) { $Before.status } else { "idle" }
    $aStatus = if ($After.status) { $After.status } else { "idle" }
    if ($bStatus -ne $aStatus) {
        $diff += "  status: $bStatus -> $aStatus"
    }
    
    # 栈变化
    $lenBefore = Get-StackDepth $Before.stack
    $lenAfter = Get-StackDepth $After.stack
    
    if ($lenAfter -gt $lenBefore) {
        # 压栈 - 只报告新增的帧数
        $diff += "+ stack: depth $lenBefore -> $lenAfter"
        $topFrame = Get-StackTop $After.stack
        if ($topFrame) {
            $argsStr = Format-ArgsBrief $topFrame.args
            $diff += "  new top: $($topFrame.function)$argsStr"
        }
    } elseif ($lenAfter -lt $lenBefore) {
        # 出栈
        $diff += "- stack: depth $lenBefore -> $lenAfter"
        if ($lenAfter -gt 0) {
            $topFrame = Get-StackTop $After.stack
            if ($topFrame) {
                $diff += "  new top: $($topFrame.function)"
            }
        }
    } elseif ($lenBefore -gt 0 -and $lenAfter -gt 0) {
        # 栈深度不变，检查栈顶是否变化 (tail_call)
        $bTop = Get-StackTop $Before.stack
        $aTop = Get-StackTop $After.stack
        if ($bTop -and $aTop -and $bTop.function -ne $aTop.function) {
            $argsStr = Format-ArgsBrief $aTop.args
            $diff += "> stack top: $($bTop.function) -> $($aTop.function)$argsStr"
        }
    }
    
    # 检查同位置帧的 prev 和 vars 变化
    $minLen = [Math]::Min($lenBefore, $lenAfter)
    for ($i = 0; $i -lt $minLen; $i++) {
        $bFrame = if ($Before.stack) { $Before.stack[$i] } else { $null }
        $aFrame = if ($After.stack) { $After.stack[$i] } else { $null }
        
        if ($bFrame -and $aFrame -and $bFrame.function -eq $aFrame.function) {
            # prev 变化
            $bPrev = $bFrame.prev
            $aPrev = $aFrame.prev
            if ($bPrev -ne $aPrev) {
                if (-not $bPrev -and $aPrev) {
                    $prevPreview = if ($aPrev.Length -gt 30) { $aPrev.Substring(0, 30) + "..." } else { $aPrev }
                    $diff += "+ stack[$i].prev: $prevPreview"
                } elseif ($bPrev -and -not $aPrev) {
                    $diff += "- stack[$i].prev: cleared"
                } else {
                    $diff += "~ stack[$i].prev: updated"
                }
            }
            
            # vars 变化
            $bVars = $bFrame.vars
            $aVars = $aFrame.vars
            $bVarsJson = if ($bVars) { $bVars | ConvertTo-Json -Compress } else { "{}" }
            $aVarsJson = if ($aVars) { $aVars | ConvertTo-Json -Compress } else { "{}" }
            if ($bVarsJson -ne $aVarsJson) {
                $diff += "~ stack[$i].vars: updated"
            }
            
            # step_index 变化
            if ($bFrame.step_index -ne $aFrame.step_index) {
                $diff += "~ stack[$i].step_index: $($bFrame.step_index) -> $($aFrame.step_index)"
            }
        }
    }
    
    # 输出变化
    if ($Before.output -ne $After.output) {
        if (-not $Before.output -and $After.output) {
            $diff += "+ output: set"
        } elseif ($Before.output -and -not $After.output) {
            $diff += "- output: cleared"
        } else {
            $diff += "~ output: changed"
        }
    }
    
    return $diff
}

function Print-Result {
    param(
        [string]$Operation,
        [string]$SessionId,
        [object]$Before,
        [object]$After,
        [string]$Error
    )
    
    Write-Host ""
    Write-Host "[$($Operation.ToUpper())] session=$SessionId"
    
    if ($Error) {
        Write-Host "[ERROR] $Error"
        Write-Host "STATE: $(Format-StateSummary $Before)"
        exit 1
    }
    
    Write-Host "BEFORE: $(Format-StateSummary $Before)"
    Write-Host "AFTER:  $(Format-StateSummary $After)"
    
    $diff = Compute-Diff $Before $After
    if ($diff.Count -gt 0) {
        Write-Host "DIFF:"
        $diff | ForEach-Object { Write-Host $_ }
    } else {
        Write-Host "DIFF: (no changes)"
    }
    
    Write-Host "[OK]"
}

# ============== 操作实现 ==============

function Op-Init {
    $before = Load-State $Session
    $after = @{ status = "idle"; stack = @(); output = $null }
    Save-State $Session $after
    Print-Result "init" $Session $before $after
}

function Op-Push {
    if (-not $Fn) {
        $before = Load-State $Session
        $errMsg = "Missing -Fn <fqn>`nUsage: stack_ops.ps1 -Session $Session -Op push -Fn <fqn> [-ArgList `"k=v,k2=v2`"]"
        Print-Result "push" $Session $before $before $errMsg
        return
    }
    
    $before = Load-State $Session
    $after = Clone-State $before
    
    $frame = @{ function = $Fn }
    if ($Arg -and $Arg.Keys.Count -gt 0) { $frame.args = $Arg }
    if ($StepIndex -ge 0) { $frame.step_index = $StepIndex }
    
    if (-not $after.stack) { $after.stack = @() }
    $after.stack = @($after.stack) + $frame
    $after.status = "running"
    
    Save-State $Session $after
    Print-Result "push" $Session $before $after
}

function Op-Pop {
    $before = Load-State $Session -MustExist $true
    
    if (-not $before.stack -or $before.stack.Count -eq 0) {
        Print-Result "pop" $Session $before $before "Cannot pop: stack is empty"
        return
    }
    
    $after = Clone-State $before
    $stack = @($after.stack)
    if ($stack.Count -gt 1) {
        $stack = $stack[0..($stack.Count - 2)]
    } else {
        $stack = @()
    }
    $after.stack = $stack
    
    if ($Output) {
        $current = if ($after.output) { $after.output } else { "" }
        if ($current) {
            $after.output = "$current`n$Output"
        } else {
            $after.output = $Output
        }
    }
    
    if ($after.stack.Count -eq 0) {
        $after.status = "idle"
    }
    
    Save-State $Session $after
    Print-Result "pop" $Session $before $after
}

function Op-TailCall {
    if (-not $Fn) {
        $before = Load-State $Session
        $errMsg = "Missing -Fn <fqn>`nUsage: stack_ops.ps1 -Session $Session -Op tail_call -Fn <fqn> [-ArgList `"k=v,k2=v2`"]"
        Print-Result "tail_call" $Session $before $before $errMsg
        return
    }
    
    $before = Load-State $Session -MustExist $true
    
    if (-not $before.stack -or $before.stack.Count -eq 0) {
        Print-Result "tail_call" $Session $before $before "Cannot tail_call: stack is empty"
        return
    }
    
    $after = Clone-State $before
    $stack = @($after.stack)
    if ($stack.Count -gt 1) {
        $stack = $stack[0..($stack.Count - 2)]
    } else {
        $stack = @()
    }
    
    $frame = @{ function = $Fn }
    if ($Arg -and $Arg.Keys.Count -gt 0) { $frame.args = $Arg }
    if ($StepIndex -ge 0) { $frame.step_index = $StepIndex }
    
    $after.stack = @($stack) + $frame
    
    Save-State $Session $after
    Print-Result "tail_call" $Session $before $after
}

function Op-Return {
    $before = Load-State $Session -MustExist $true
    
    if (-not $before.stack -or $before.stack.Count -eq 0) {
        Print-Result "return" $Session $before $before "Cannot return: stack is empty"
        return
    }
    
    $after = Clone-State $before
    $stack = @($after.stack)
    if ($stack.Count -gt 1) {
        $stack = $stack[0..($stack.Count - 2)]
    } else {
        $stack = @()
    }
    $after.stack = $stack
    
    $returnValue = if ($Value) { $Value } else { $null }
    if ($returnValue) {
        # 1. 写入父帧的 prev 字段 (用于 sequence 中的 $prev 引用)
        if ($after.stack.Count -gt 0) {
            $parentIdx = $after.stack.Count - 1
            $after.stack[$parentIdx] | Add-Member -NotePropertyName "prev" -NotePropertyValue $returnValue -Force
        }
        
        # 2. 追加到会话输出
        $current = if ($after.output) { $after.output } else { "" }
        if ($current) {
            $after.output = "$current`n$returnValue"
        } else {
            $after.output = $returnValue
        }
    }
    
    if ($after.stack.Count -eq 0) {
        $after.status = "idle"
    }
    
    Save-State $Session $after
    Print-Result "return" $Session $before $after
}

function Op-Update {
    $before = Load-State $Session -MustExist $true
    
    if (-not $before.stack -or $before.stack.Count -eq 0) {
        Print-Result "update" $Session $before $before "Cannot update: stack is empty"
        return
    }
    
    $after = Clone-State $before
    $idx = $after.stack.Count - 1
    $topFrame = $after.stack[$idx]
    
    if ($StepIndex -ge 0) {
        $topFrame | Add-Member -NotePropertyName "step_index" -NotePropertyValue $StepIndex -Force
    }
    if ($Output) {
        $topFrame | Add-Member -NotePropertyName "output" -NotePropertyValue $Output -Force
    }
    if ($Prev) {
        $topFrame | Add-Member -NotePropertyName "prev" -NotePropertyValue $Prev -Force
    }
    if ($VarList) {
        # 解析 "k1=v1,k2=v2" 格式
        $vars = Parse-ArgList $VarList
        if (-not $topFrame.vars) {
            $topFrame | Add-Member -NotePropertyName "vars" -NotePropertyValue @{} -Force
        }
        foreach ($key in $vars.Keys) {
            if ($topFrame.vars -is [hashtable]) {
                $topFrame.vars[$key] = $vars[$key]
            } else {
                $topFrame.vars | Add-Member -NotePropertyName $key -NotePropertyValue $vars[$key] -Force
            }
        }
    }
    
    Save-State $Session $after
    Print-Result "update" $Session $before $after
}

function Op-Peek {
    $state = Load-State $Session -MustExist $true
    
    Write-Host ""
    Write-Host "[PEEK] session=$Session"
    Write-Host "STATE: $(Format-StateSummary $state)"
    
    if (-not $state.stack -or $state.stack.Count -eq 0) {
        Write-Host "TOP: (empty)"
    } else {
        $idx = $state.stack.Count - 1
        $top = $state.stack[$idx]
        Write-Host "TOP[$idx]: $($top.function)"
        if ($top.args) {
            Write-Host "  args: $($top.args | ConvertTo-Json -Compress)"
        }
        if ($null -ne $top.step_index) {
            Write-Host "  step_index: $($top.step_index)"
        }
        if ($top.prev) {
            Write-Host "  prev: $($top.prev | ConvertTo-Json -Compress)"
        }
        if ($top.vars) {
            Write-Host "  vars: $($top.vars | ConvertTo-Json -Compress)"
        }
    }
}

function Op-Show {
    $state = Load-State $Session -MustExist $true
    $file = Get-StateFile $Session
    
    Write-Host ""
    Write-Host "[SHOW] session=$Session"
    Write-Host "file: $file"
    Write-Host "status: $($state.status)"
    
    $stack = if ($state.stack) { @($state.stack) } else { @() }
    Write-Host "stack: [$($stack.Count)]"
    
    if ($stack.Count -eq 0) {
        Write-Host "  (empty)"
    } else {
        for ($i = 0; $i -lt $stack.Count; $i++) {
            $frame = $stack[$i]
            $line = "  [$i] $($frame.function)"
            if ($frame.args) {
                $argsStr = ($frame.args | ConvertTo-Json -Compress)
                $line += " args=$argsStr"
            }
            if ($null -ne $frame.step_index) {
                $line += " step=$($frame.step_index)"
            }
            if ($frame.prev) {
                $prevPreview = if ($frame.prev.Length -gt 20) { $frame.prev.Substring(0, 20) + "..." } else { $frame.prev }
                $line += " prev=`"$prevPreview`""
            }
            if ($frame.vars) {
                $varsStr = ($frame.vars | ConvertTo-Json -Compress)
                $line += " vars=$varsStr"
            }
            Write-Host $line
        }
    }
    
    if ($state.output) {
        Write-Host ""
        Write-Host "output:"
        Write-Host $state.output
    }
}

function Op-Clear {
    $before = Load-State $Session
    $after = @{ status = "idle"; stack = @(); output = $null }
    Save-State $Session $after
    Print-Result "clear" $Session $before $after
}

function Op-SetStatus {
    $statusVal = if ($Status) { $Status } elseif ($Value) { $Value } else { $null }
    
    if (-not $statusVal -or $statusVal -notin @("idle", "running")) {
        $before = Load-State $Session
        $errMsg = "Missing or invalid -Value <idle|running>`nUsage: stack_ops.ps1 -Session $Session -Op set_status -Value idle"
        Print-Result "set_status" $Session $before $before $errMsg
        return
    }
    
    $before = Load-State $Session
    $after = Clone-State $before
    $after.status = $statusVal
    
    Save-State $Session $after
    Print-Result "set_status" $Session $before $after
}

function Op-SetOutput {
    if (-not $Value) {
        $before = Load-State $Session
        $errMsg = "Missing -Value <output>`nUsage: stack_ops.ps1 -Session $Session -Op set_output -Value `"your output`""
        Print-Result "set_output" $Session $before $before $errMsg
        return
    }
    
    $before = Load-State $Session
    $after = Clone-State $before
    $after.output = $Value
    
    Save-State $Session $after
    Print-Result "set_output" $Session $before $after
}

function Op-SetVar {
    if (-not $VarList) {
        $before = Load-State $Session
        $errMsg = "Missing -VarList `"k=v,...`"`nUsage: stack_ops.ps1 -Session $Session -Op set_var -VarList `"x=1,name=test`""
        Print-Result "set_var" $Session $before $before $errMsg
        return
    }
    
    $before = Load-State $Session -MustExist $true
    
    if (-not $before.stack -or $before.stack.Count -eq 0) {
        Print-Result "set_var" $Session $before $before "Cannot set_var: stack is empty"
        return
    }
    
    # 解析变量列表
    $vars = Parse-ArgList $VarList
    if ($vars.Keys.Count -eq 0) {
        Print-Result "set_var" $Session $before $before "No valid key=value pairs in VarList"
        return
    }
    
    $after = Clone-State $before
    $idx = $after.stack.Count - 1
    $topFrame = $after.stack[$idx]
    
    # 初始化 vars
    if (-not $topFrame.vars) {
        $topFrame | Add-Member -NotePropertyName "vars" -NotePropertyValue @{} -Force
    }
    
    # 批量设置变量
    foreach ($key in $vars.Keys) {
        if ($topFrame.vars -is [hashtable]) {
            $topFrame.vars[$key] = $vars[$key]
        } else {
            $topFrame.vars | Add-Member -NotePropertyName $key -NotePropertyValue $vars[$key] -Force
        }
    }
    
    Save-State $Session $after
    Print-Result "set_var" $Session $before $after
}

function Op-GetVar {
    if (-not $Key) {
        Write-Host ""
        Write-Host "[GET_VAR] session=$Session"
        Write-Host "[ERROR] Missing -Key <key>"
        Write-Host "Usage: stack_ops.ps1 -Session $Session -Op get_var -Key <key>"
        return
    }
    
    $state = Load-State $Session -MustExist $true
    
    if (-not $state.stack -or $state.stack.Count -eq 0) {
        Write-Host ""
        Write-Host "[GET_VAR] session=$Session"
        Write-Host "[ERROR] Cannot get_var: stack is empty"
        return
    }
    
    $idx = $state.stack.Count - 1
    $topFrame = $state.stack[$idx]
    
    # 查找顺序: vars > args > prev
    $value = $null
    $source = $null
    
    # 检查 vars
    if ($topFrame.vars) {
        if ($topFrame.vars -is [hashtable] -and $topFrame.vars.ContainsKey($Key)) {
            $value = $topFrame.vars[$Key]
            $source = "vars"
        } elseif ($topFrame.vars.PSObject.Properties[$Key]) {
            $value = $topFrame.vars.$Key
            $source = "vars"
        }
    }
    
    # 检查 args
    if ($null -eq $value -and $topFrame.args) {
        if ($topFrame.args -is [hashtable] -and $topFrame.args.ContainsKey($Key)) {
            $value = $topFrame.args[$Key]
            $source = "args"
        } elseif ($topFrame.args.PSObject.Properties[$Key]) {
            $value = $topFrame.args.$Key
            $source = "args"
        }
    }
    
    # 检查 prev (特殊键)
    if ($null -eq $value -and $Key -eq "prev" -and $topFrame.prev) {
        $value = $topFrame.prev
        $source = "prev"
    }
    
    Write-Host ""
    Write-Host "[GET_VAR] session=$Session"
    Write-Host "KEY: $Key"
    if ($null -ne $value) {
        $jsonValue = $value | ConvertTo-Json -Compress
        Write-Host "VALUE: $jsonValue"
        Write-Host "SOURCE: $source"
    } else {
        Write-Host "VALUE: (not found)"
    }
}

function Op-DelVar {
    if (-not $Keys) {
        $before = Load-State $Session
        $errMsg = "Missing -Keys `"k1,k2,...`"`nUsage: stack_ops.ps1 -Session $Session -Op del_var -Keys `"x,y`""
        Print-Result "del_var" $Session $before $before $errMsg
        return
    }
    
    $before = Load-State $Session -MustExist $true
    
    if (-not $before.stack -or $before.stack.Count -eq 0) {
        Print-Result "del_var" $Session $before $before "Cannot del_var: stack is empty"
        return
    }
    
    $after = Clone-State $before
    $idx = $after.stack.Count - 1
    $topFrame = $after.stack[$idx]
    
    if (-not $topFrame.vars) {
        Print-Result "del_var" $Session $before $before "No vars to delete (vars is empty)"
        return
    }
    
    # 解析 key 列表
    $keyList = $Keys.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    
    # 检查哪些 key 存在
    $notFound = @()
    foreach ($key in $keyList) {
        $exists = $false
        if ($topFrame.vars -is [hashtable]) {
            $exists = $topFrame.vars.ContainsKey($key)
        } elseif ($topFrame.vars.PSObject.Properties[$key]) {
            $exists = $true
        }
        if (-not $exists) {
            $notFound += $key
        }
    }
    
    if ($notFound.Count -gt 0) {
        Print-Result "del_var" $Session $before $before "Variable(s) not found in vars: $($notFound -join ', ')"
        return
    }
    
    # 批量删除
    foreach ($key in $keyList) {
        if ($topFrame.vars -is [hashtable]) {
            $topFrame.vars.Remove($key)
        } else {
            $topFrame.vars.PSObject.Properties.Remove($key)
        }
    }
    
    # 如果 vars 为空，移除整个字段
    $isEmpty = $true
    if ($topFrame.vars -is [hashtable]) {
        $isEmpty = $topFrame.vars.Count -eq 0
    } elseif ($topFrame.vars.PSObject.Properties) {
        $isEmpty = @($topFrame.vars.PSObject.Properties).Count -eq 0
    }
    
    if ($isEmpty) {
        $topFrame.PSObject.Properties.Remove("vars")
    }
    
    Save-State $Session $after
    Print-Result "del_var" $Session $before $after
}

# ============== 主入口 ==============

switch ($Op) {
    "init"       { Op-Init }
    "push"       { Op-Push }
    "call"       { Op-Push }
    "pop"        { Op-Pop }
    "tail_call"  { Op-TailCall }
    "return"     { Op-Return }
    "update"     { Op-Update }
    "peek"       { Op-Peek }
    "show"       { Op-Show }
    "clear"      { Op-Clear }
    "set_status" { Op-SetStatus }
    "set_output" { Op-SetOutput }
    "set_var"    { Op-SetVar }
    "get_var"    { Op-GetVar }
    "del_var"    { Op-DelVar }
    default      { Write-Host "[ERROR] Unknown operation: $Op"; exit 1 }
}
