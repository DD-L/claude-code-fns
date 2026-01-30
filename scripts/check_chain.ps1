# Stop Hook - Check if function chain needs to continue
# Uses WT_SESSION environment variable to identify the session
# exit 0: allow stop
# exit 2 + stderr: block stop, stderr content is fed back to Claude

$StatesDir = "$PSScriptRoot\states"

if (-not (Test-Path $StatesDir)) {
    exit 0
}

$logFile = "$StatesDir\.hook_debug.log"
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

$inputJson = ""
try {
    $inputJson = [Console]::In.ReadToEnd()
} catch {
}

Add-Content -Path $logFile -Value "[$timestamp] Stop hook triggered" -Encoding UTF8
Add-Content -Path $logFile -Value "[$timestamp] WT_SESSION: $env:WT_SESSION" -Encoding UTF8
Add-Content -Path $logFile -Value "[$timestamp] Input length: $($inputJson.Length)" -Encoding UTF8

$stopHookActive = $false
if ($inputJson) {
    try {
        $inputObj = $inputJson | ConvertFrom-Json
        $stopHookActive = $inputObj.stop_hook_active
        Add-Content -Path $logFile -Value "[$timestamp] Parsed stop_hook_active: $stopHookActive" -Encoding UTF8
    } catch {
        Add-Content -Path $logFile -Value "[$timestamp] JSON parse error: $_" -Encoding UTF8
    }
}

if ($stopHookActive -eq $true) {
    Add-Content -Path $logFile -Value "[$timestamp] stop_hook_active=true, allowing stop" -Encoding UTF8
    exit 0
}

$wtSession = $env:WT_SESSION
if (-not $wtSession) {
    Add-Content -Path $logFile -Value "[$timestamp] No WT_SESSION, allowing stop" -Encoding UTF8
    exit 0
}

$StateFile = "$StatesDir\$wtSession.json"
Add-Content -Path $logFile -Value "[$timestamp] Checking state file: $StateFile" -Encoding UTF8

if (-not (Test-Path $StateFile)) {
    Add-Content -Path $logFile -Value "[$timestamp] State file not found, allowing stop" -Encoding UTF8
    exit 0
}

try {
    $state = Get-Content $StateFile -Raw -Encoding UTF8 | ConvertFrom-Json
} catch {
    Add-Content -Path $logFile -Value "[$timestamp] Failed to parse state file: $_" -Encoding UTF8
    exit 0
}

# Check stack count directly from array (authoritative source, not depth field)
$stackLen = if ($state.stack) { $state.stack.Count } else { 0 }
$status = if ($state.status) { $state.status } else { "idle" }

# Always log state info for audit
Add-Content -Path $logFile -Value "[$timestamp] State: status=$status, stack_len=$stackLen" -Encoding UTF8

if ($stackLen -gt 0) {
    $topFrame = $state.stack[-1]
    
    # Log warning for stack leak (idle but stack not empty)
    if ($status -eq "idle") {
        Add-Content -Path $logFile -Value "[$timestamp] WARNING: Stack leak detected! status=idle but stack_len=$stackLen" -Encoding UTF8
    }
    
    Add-Content -Path $logFile -Value "[$timestamp] Stack NOT empty! Blocking stop." -Encoding UTF8
    Add-Content -Path $logFile -Value "[$timestamp]   Top frame: $($topFrame.function)" -Encoding UTF8
    
    # Log call chain
    if ($stackLen -gt 1) {
        $chainFns = @()
        foreach ($frame in $state.stack) { $chainFns += $frame.function }
        Add-Content -Path $logFile -Value "[$timestamp]   Call chain: $($chainFns -join ' -> ')" -Encoding UTF8
    }
    
    # Build user-friendly message
    $leakNote = if ($status -eq "idle") { " [LEAK]" } else { "" }
    $msg = "[!][STOP-HOOK] Cannot stop: Stack not empty$leakNote"
    $msg += "`n  Session: $wtSession"
    $msg += "`n  Stack depth: $stackLen"
    
    # Top frame with args
    $topFn = $topFrame.function
    if ($topFrame.args) {
        try {
            $argPairs = @()
            $topFrame.args.PSObject.Properties | ForEach-Object {
                $argPairs += "$($_.Name)=$($_.Value)"
            }
            if ($argPairs.Count -gt 0) {
                $topFn += " ($($argPairs -join ', '))"
            }
        } catch {}
    }
    $msg += "`n  Top frame: $topFn"
    
    # Call chain (show all frames with arrow)
    if ($stackLen -ge 1) {
        $chainParts = @()
        $showCount = [Math]::Min($stackLen, 5)
        $startIdx = $stackLen - $showCount
        if ($startIdx -gt 0) {
            $chainParts += "..."
        }
        for ($i = $startIdx; $i -lt $stackLen; $i++) {
            $chainParts += $state.stack[$i].function
        }
        $msg += "`n  Call chain: $($chainParts -join ' -> ')"
    }
    
    $msg += "`n  To continue: /fn_continue --session=$wtSession"
    
    [Console]::Error.WriteLine($msg)
    exit 2
}

# Task complete - output brief info
$outputInfo = ""
if ($state.output) {
    $outStr = "$($state.output)"
    if ($outStr.Length -gt 100) {
        $outStr = $outStr.Substring(0, 97) + "..."
    }
    $outputInfo = " | output: $outStr"
}
Add-Content -Path $logFile -Value "[$timestamp] Stack empty (stack_len=0), allowing stop" -Encoding UTF8

# Brief completion message to stderr (informational, still exit 0)
$completeMsg = "[ok] $wtSession | idle$outputInfo"
[Console]::Error.WriteLine($completeMsg)
exit 0
