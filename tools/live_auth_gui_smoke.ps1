[CmdletBinding()]
param(
    [ValidateRange(1, 60)]
    [int]$HoldSeconds = 5
)

$ErrorActionPreference = "Stop"
$tempRoot = if ($env:RUNNER_TEMP) {
    (Resolve-Path -LiteralPath $env:RUNNER_TEMP -ErrorAction Stop).Path
} else {
    [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
}
$smokeHome = Join-Path $tempRoot ("coupuas-live-auth-" + [guid]::NewGuid().ToString("N"))
$roamingDir = Join-Path $smokeHome "AppData\Roaming"
$localDir = Join-Path $smokeHome "AppData\Local"
New-Item -ItemType Directory -Force -Path $roamingDir, $localDir | Out-Null

$environmentKeys = @(
    "USERPROFILE",
    "HOME",
    "APPDATA",
    "LOCALAPPDATA",
    "QT_QPA_PLATFORM",
    "THREAD_AUTO_DISABLE_AUTOSTART_SYNC",
    "THREAD_AUTO_DISABLE_AUTO_UPDATE",
    "THREAD_AUTO_DISABLE_HEARTBEAT",
    "THREAD_AUTO_DISABLE_RESUME_PROMPT"
)
$previousEnvironment = @{}
foreach ($key in $environmentKeys) {
    $previousEnvironment[$key] = [Environment]::GetEnvironmentVariable($key, "Process")
}

try {
    $env:USERPROFILE = $smokeHome
    $env:HOME = $smokeHome
    $env:APPDATA = $roamingDir
    $env:LOCALAPPDATA = $localDir
    $env:QT_QPA_PLATFORM = "offscreen"
    $env:THREAD_AUTO_DISABLE_AUTOSTART_SYNC = "1"
    $env:THREAD_AUTO_DISABLE_AUTO_UPDATE = "1"
    $env:THREAD_AUTO_DISABLE_HEARTBEAT = "1"
    $env:THREAD_AUTO_DISABLE_RESUME_PROMPT = "1"

    & python "tools/live_auth_ui_smoke.py" `
        --confirm-live-account `
        --hold-seconds $HoldSeconds
    if ($LASTEXITCODE -ne 0) {
        throw "Live authentication GUI smoke failed with exit code $LASTEXITCODE."
    }
} finally {
    foreach ($key in $environmentKeys) {
        [Environment]::SetEnvironmentVariable($key, $previousEnvironment[$key], "Process")
    }

    if (Test-Path -LiteralPath $smokeHome) {
        $resolvedSmokeHome = (Resolve-Path -LiteralPath $smokeHome).Path
        $insideTempRoot = $resolvedSmokeHome.StartsWith(
            $tempRoot + [IO.Path]::DirectorySeparatorChar,
            [StringComparison]::OrdinalIgnoreCase
        )
        if (-not $insideTempRoot) {
            throw "Refusing to remove live-auth smoke data outside the temporary directory."
        }
        Remove-Item -LiteralPath $resolvedSmokeHome -Recurse -Force
    }
}
