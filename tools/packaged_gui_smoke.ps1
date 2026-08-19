[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ExePath,

    [ValidateRange(10, 180)]
    [int]$TimeoutSeconds = 60
)

$ErrorActionPreference = "Stop"
$resolvedExe = (Resolve-Path -LiteralPath $ExePath -ErrorAction Stop).Path
if ([IO.Path]::GetExtension($resolvedExe) -ne ".exe") {
    throw "Packaged GUI smoke requires a Windows executable."
}

$tempRoot = if ($env:RUNNER_TEMP) {
    (Resolve-Path -LiteralPath $env:RUNNER_TEMP -ErrorAction Stop).Path
} else {
    [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
}
$smokeHome = Join-Path $tempRoot ("coupuas-packaged-gui-" + [guid]::NewGuid().ToString("N"))
$roamingDir = Join-Path $smokeHome "AppData\Roaming"
$localDir = Join-Path $smokeHome "AppData\Local"
New-Item -ItemType Directory -Force -Path $roamingDir, $localDir | Out-Null

$environmentKeys = @(
    "USERPROFILE",
    "HOME",
    "APPDATA",
    "LOCALAPPDATA",
    "THREAD_AUTO_DISABLE_AUTOSTART_SYNC",
    "THREAD_AUTO_DISABLE_AUTO_UPDATE",
    "THREAD_AUTO_DISABLE_HEARTBEAT",
    "THREAD_AUTO_DISABLE_RESUME_PROMPT"
)
$previousEnvironment = @{}
foreach ($key in $environmentKeys) {
    $previousEnvironment[$key] = [Environment]::GetEnvironmentVariable($key, "Process")
}

$process = $null
$windowProcess = $null
function Get-DescendantProcessIds {
    param([Parameter(Mandatory = $true)][int]$RootProcessId)

    $seen = [Collections.Generic.HashSet[int]]::new()
    $pending = [Collections.Generic.Queue[int]]::new()
    [void]$seen.Add($RootProcessId)
    $pending.Enqueue($RootProcessId)
    while ($pending.Count -gt 0) {
        $currentId = $pending.Dequeue()
        $children = @(
            Get-CimInstance -ClassName Win32_Process `
                -Filter "ParentProcessId = $currentId" `
                -ErrorAction SilentlyContinue
        )
        foreach ($child in $children) {
            $childId = [int]$child.ProcessId
            if ($seen.Add($childId)) {
                $pending.Enqueue($childId)
            }
        }
    }
    @($seen)
}

function Get-SmokeProcesses {
    if (-not $process) {
        return @()
    }
    $processIds = @(Get-DescendantProcessIds -RootProcessId $process.Id)
    @(Get-Process -Id $processIds -ErrorAction SilentlyContinue)
}

try {
    $env:USERPROFILE = $smokeHome
    $env:HOME = $smokeHome
    $env:APPDATA = $roamingDir
    $env:LOCALAPPDATA = $localDir
    $env:THREAD_AUTO_DISABLE_AUTOSTART_SYNC = "1"
    $env:THREAD_AUTO_DISABLE_AUTO_UPDATE = "1"
    $env:THREAD_AUTO_DISABLE_HEARTBEAT = "1"
    $env:THREAD_AUTO_DISABLE_RESUME_PROMPT = "1"

    $process = Start-Process -FilePath $resolvedExe -PassThru
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $windowProcess = Get-SmokeProcesses |
            Where-Object {
                $_.MainWindowHandle -ne 0 -and
                $_.Responding -and
                $_.MainWindowTitle -eq "스레드 쇼핑 자동화 - 로그인"
            } |
            Select-Object -First 1
        if ($windowProcess) {
            break
        }
        Start-Sleep -Milliseconds 200
    }

    if (-not $windowProcess) {
        throw "Packaged application did not show a login window within $TimeoutSeconds seconds."
    }
    $windowProcess.Refresh()
    if (-not $windowProcess.Responding) {
        throw "Packaged login window is not responding."
    }
    if ($windowProcess.MainWindowTitle -ne "스레드 쇼핑 자동화 - 로그인") {
        throw "Unexpected packaged window title: '$($windowProcess.MainWindowTitle)'"
    }

    if (-not $windowProcess.CloseMainWindow()) {
        throw "Packaged login window rejected a graceful close request."
    }
    $exitDeadline = (Get-Date).AddSeconds(15)
    while ((Get-SmokeProcesses).Count -gt 0 -and (Get-Date) -lt $exitDeadline) {
        Start-Sleep -Milliseconds 200
    }
    if ((Get-SmokeProcesses).Count -gt 0) {
        throw "Packaged application did not exit cleanly after closing the login window."
    }
    if (-not $process.HasExited -and -not $process.WaitForExit(15000)) {
        throw "Packaged bootloader did not exit after the login window closed."
    }
    $process.Refresh()
    if ($process.ExitCode -ne 0) {
        throw "Packaged application returned a non-zero exit code: $($process.ExitCode)"
    }

    Write-Host "[OK] Signed packaged login window launched, responded, and exited cleanly."
} finally {
    foreach ($smokeProcess in Get-SmokeProcesses) {
        Stop-Process -Id $smokeProcess.Id -Force -ErrorAction SilentlyContinue
    }
    $cleanupDeadline = (Get-Date).AddSeconds(10)
    while ((Get-SmokeProcesses).Count -gt 0 -and (Get-Date) -lt $cleanupDeadline) {
        Start-Sleep -Milliseconds 100
    }
    if ((Get-SmokeProcesses).Count -gt 0) {
        throw "Packaged GUI smoke processes did not terminate during cleanup."
    }
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
            throw "Refusing to remove GUI smoke data outside the temporary directory."
        }
        Remove-Item -LiteralPath $resolvedSmokeHome -Recurse -Force
    }
}
