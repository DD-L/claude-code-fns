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

Add-Content -Path $logFile -Value "[$timestamp] Stop hook triggered"
Add-Content -Path $logFile -Value "[$timestamp] WT_SESSION: $env:WT_SESSION"
Add-Content -Path $logFile -Value "[$timestamp] Input length: $($inputJson.Length)"

$stopHookActive = $false
if ($inputJson) {
    try {
        $inputObj = $inputJson | ConvertFrom-Json
        $stopHookActive = $inputObj.stop_hook_active
        Add-Content -Path $logFile -Value "[$timestamp] Parsed stop_hook_active: $stopHookActive"
    } catch {
        Add-Content -Path $logFile -Value "[$timestamp] JSON parse error: $_"
    }
}

if ($stopHookActive -eq $true) {
    Add-Content -Path $logFile -Value "[$timestamp] stop_hook_active=true, allowing stop"
    exit 0
}

$wtSession = $env:WT_SESSION
if (-not $wtSession) {
    Add-Content -Path $logFile -Value "[$timestamp] No WT_SESSION, allowing stop"
    exit 0
}

$StateFile = "$StatesDir\$wtSession.json"
Add-Content -Path $logFile -Value "[$timestamp] Checking state file: $StateFile"

if (-not (Test-Path $StateFile)) {
    Add-Content -Path $logFile -Value "[$timestamp] State file not found, allowing stop"
    exit 0
}

try {
    $state = Get-Content $StateFile -Raw | ConvertFrom-Json
} catch {
    Add-Content -Path $logFile -Value "[$timestamp] Failed to parse state file: $_"
    exit 0
}

if ($state.status -eq "running" -and $state.stack -and $state.stack.Count -gt 0) {
    $depth = $state.stack.Count
    $topFrame = $state.stack[-1]
    
    Add-Content -Path $logFile -Value "[$timestamp] Stack NOT empty! Blocking stop."
    
    # Build message
    $msg = "[STOP-HOOK] Stack NOT empty ($depth frame$(if($depth -gt 1){'s'}))"
    $msg += "`nTop: $($topFrame.function)"
    
    # Show top frame args (compact JSON)
    if ($topFrame.args) {
        try {
            $argsJson = $topFrame.args | ConvertTo-Json -Compress -Depth 2
            $msg += "`nArgs: $argsJson"
        } catch {}
    }
    
    # Show simple stack trace (max 5 frames from top)
    if ($depth -gt 1) {
        $msg += "`nStack (bottom to top):"
        $showCount = [Math]::Min($depth, 5)
        $startIdx = $depth - $showCount
        if ($startIdx -gt 0) {
            $msg += "`n  ... ($startIdx more)"
        }
        for ($i = $startIdx; $i -lt $depth; $i++) {
            $frame = $state.stack[$i]
            $pointer = if ($i -eq $depth - 1) { " <- TOP" } else { "" }
            $msg += "`n  [$i] $($frame.function)$pointer"
        }
    }
    
    $msg += "`nYou MUST continue until stack is empty. Run: /fn_continue"
    
    [Console]::Error.WriteLine($msg)
    exit 2
}

Add-Content -Path $logFile -Value "[$timestamp] Stack empty or not running, allowing stop"
exit 0
