# Get session_id (WT_SESSION) for use in fn-controller / stack_ops
# Usage:
#   PowerShell:        .\get_session_id.ps1   or  pwsh -File scripts/get_session_id.ps1
#   Git Bash (sourced): eval "$(powershell -NoProfile -Command "& { . ./scripts/get_session_id.ps1; Get-SessionId -Format Bash }")"
#
# Output formats:
#   - Default: raw value only (for piping)
#   - Format PowerShell: echo "WT_SESSION=$env:WT_SESSION"
#   - Format Bash:      echo "WT_SESSION=$WT_SESSION"  (when run in bash, $WT_SESSION is the var)

param(
    [ValidateSet('', 'Raw', 'PowerShell', 'Bash')]
    [string]$Format = 'Raw'
)

function Get-SessionId {
    param([string]$Format = 'Raw')
    $sid = $env:WT_SESSION
    if ($Format -eq 'PowerShell') {
        Write-Output "echo `"WT_SESSION=`$env:WT_SESSION`""
        return
    }
    if ($Format -eq 'Bash') {
        # Output export form for bash: WT_SESSION=value (so bash can eval this)
        if ($sid) {
            Write-Output "WT_SESSION=$sid"
        } else {
            Write-Output "WT_SESSION="
        }
        return
    }
    # Raw: only the value
    Write-Output $sid
}

Get-SessionId -Format $Format
