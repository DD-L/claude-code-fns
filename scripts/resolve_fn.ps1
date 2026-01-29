# Function Resolver - PowerShell version
# Static function dispatch resolver
#
# Usage:
#   .\resolve_fn.ps1 <target_ref> [-Caller <caller_fqn>]
#
# Examples:
#   .\resolve_fn.ps1 validate
#   .\resolve_fn.ps1 validate -Caller "tests/test_sequence"
#   .\resolve_fn.ps1 examples/validate
#   .\resolve_fn.ps1 ./seq_step1 -Caller "tests/test_sequence"

param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$TargetRef,
    
    [Parameter(Mandatory=$false)]
    [string]$Caller = ""
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$FunctionsDir = Join-Path $ProjectRoot "functions"

# Built-in functions
$Builtins = @("_return", "_compact", "_clear")

function Normalize-Path {
    param([string]$Path)
    
    $parts = @()
    foreach ($part in $Path.Replace('\', '/').Split('/')) {
        if ($part -eq "..") {
            if ($parts.Count -gt 0) {
                $parts = $parts[0..($parts.Count-2)]
            }
        } elseif ($part -and $part -ne ".") {
            $parts += $part
        }
    }
    return $parts -join "/"
}

function Get-CallerDir {
    param([string]$CallerFqn)
    
    if (-not $CallerFqn) { return "" }
    if ($CallerFqn.Contains("/")) {
        $parts = $CallerFqn.Split("/")
        return ($parts[0..($parts.Count-2)] -join "/")
    }
    return ""
}

function Resolve-Function {
    param(
        [string]$CallerFqn,
        [string]$TargetRef
    )
    
    # Handle built-in functions
    if ($Builtins -contains $TargetRef) {
        return @{
            success = $true
            fqn = $TargetRef
            path = $null
            builtin = $true
        }
    }
    
    $callerDir = Get-CallerDir $CallerFqn
    
    # 1. Explicit relative path (./ or ../)
    if ($TargetRef.StartsWith("./") -or $TargetRef.StartsWith("../")) {
        if ($callerDir) {
            $resolved = Normalize-Path "$callerDir/$TargetRef"
        } else {
            $resolved = Normalize-Path $TargetRef
        }
        
        $path = Join-Path $FunctionsDir "$resolved.json"
        if (Test-Path $path) {
            return @{
                success = $true
                fqn = $resolved
                path = "functions/$resolved.json"
            }
        } else {
            return @{
                success = $false
                error = "Function not found: $TargetRef (resolved to $resolved, from $($CallerFqn -or 'root'))"
            }
        }
    }
    
    # 2. Absolute path (contains / but doesn't start with .)
    if ($TargetRef.Contains("/")) {
        $path = Join-Path $FunctionsDir "$TargetRef.json"
        if (Test-Path $path) {
            return @{
                success = $true
                fqn = $TargetRef
                path = "functions/$TargetRef.json"
            }
        } else {
            return @{
                success = $false
                error = "Function not found: $TargetRef (absolute path)"
            }
        }
    }
    
    # 3. Short name - search upward (bubble up)
    $searchDirs = @()
    $currentDir = $callerDir
    
    while ($currentDir) {
        $searchDirs += $currentDir
        if ($currentDir.Contains("/")) {
            $parts = $currentDir.Split("/")
            $currentDir = ($parts[0..($parts.Count-2)] -join "/")
        } else {
            $currentDir = ""
        }
    }
    $searchDirs += ""  # Root directory
    
    foreach ($dir in $searchDirs) {
        if ($dir) {
            $fqn = "$dir/$TargetRef"
            $path = Join-Path (Join-Path $FunctionsDir $dir) "$TargetRef.json"
        } else {
            $fqn = $TargetRef
            $path = Join-Path $FunctionsDir "$TargetRef.json"
        }
        
        if (Test-Path $path) {
            $relPath = if ($dir) { "functions/$dir/$TargetRef.json" } else { "functions/$TargetRef.json" }
            return @{
                success = $true
                fqn = $fqn
                path = $relPath
            }
        }
    }
    
    # Not found
    $searchPath = ($searchDirs | ForEach-Object { if ($_) { $_ } else { "(root)" } }) -join " -> "
    return @{
        success = $false
        error = "Function not found: $TargetRef (searched: $searchPath)"
    }
}

# Main execution
$result = Resolve-Function -CallerFqn $Caller -TargetRef $TargetRef

# Output as JSON
$result | ConvertTo-Json -Depth 10

if ($result.success) {
    exit 0
} else {
    exit 1
}
