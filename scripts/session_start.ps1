# SessionStart Hook - Record session startup
# Session ID is obtained via WT_SESSION in fn command

$statesDir = "$PSScriptRoot\states"
if (-not (Test-Path $statesDir)) {
    New-Item -ItemType Directory -Path $statesDir -Force | Out-Null
}

$inputJson = ""
try {
    $inputJson = [Console]::In.ReadToEnd()
} catch {
}

$logFile = "$statesDir\.hook_debug.log"
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

Add-Content -Path $logFile -Value "[$timestamp] SessionStart hook triggered"
Add-Content -Path $logFile -Value "[$timestamp] WT_SESSION: $env:WT_SESSION"
Add-Content -Path $logFile -Value "[$timestamp] Input length: $($inputJson.Length)"
Add-Content -Path $logFile -Value "[$timestamp] CLAUDE_ENV_FILE: $env:CLAUDE_ENV_FILE"

exit 0
