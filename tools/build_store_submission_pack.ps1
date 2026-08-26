param(
    [string]$Version = "",
    [string]$PackagePath = "",
    [switch]$SkipCapture
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

if (-not $Version) {
    $versionSource = Get-Content -Raw (Join-Path $repoRoot "src\__init__.py")
    $match = [regex]::Match($versionSource, '__version__\s*=\s*"(?<version>\d+\.\d+\.\d+)"')
    if (-not $match.Success) {
        throw "Could not resolve the application version."
    }
    $Version = "$($match.Groups['version'].Value).0"
}

if ($Version -notmatch '^\d+\.\d+\.\d+\.\d+$') {
    throw "Microsoft Store version must contain four numeric components."
}

if (-not $SkipCapture) {
    Push-Location $repoRoot
    try {
        Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
        & python "tools\capture_nordic_bento_ui.py"
        if ($LASTEXITCODE -ne 0) {
            throw "Store screenshot capture failed."
        }
    }
    finally {
        Pop-Location
    }
}

$sourceDir = Join-Path $repoRoot "output\ui-nordic"
$packDir = Join-Path $repoRoot "output\store-submission-$Version"
$screensDir = Join-Path $packDir "screenshots"

if (Test-Path -LiteralPath $packDir) {
    $resolvedOutput = [IO.Path]::GetFullPath((Join-Path $repoRoot "output"))
    $resolvedPack = [IO.Path]::GetFullPath($packDir)
    if (-not $resolvedPack.StartsWith($resolvedOutput + [IO.Path]::DirectorySeparatorChar)) {
        throw "Refusing to replace a submission pack outside output/."
    }
    Remove-Item -LiteralPath $resolvedPack -Recurse -Force
}

New-Item -ItemType Directory -Path $screensDir -Force | Out-Null

$screenshots = [ordered]@{
    "automation-wide.png" = "01-link-automation.png"
    "settings-writing.png" = "02-writing-settings.png"
    "settings-accounts.png" = "03-account-settings.png"
    "settings-ai-app.png" = "04-ai-app-settings.png"
}

Add-Type -AssemblyName System.Drawing
foreach ($entry in $screenshots.GetEnumerator()) {
    $source = Join-Path $sourceDir $entry.Key
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "Missing Store screenshot: $source"
    }

    $image = [Drawing.Image]::FromFile($source)
    try {
        if ($image.Width -lt 1366 -or $image.Height -lt 768) {
            throw "Store screenshot is below 1366 x 768: $($entry.Key) ($($image.Width) x $($image.Height))"
        }
    }
    finally {
        $image.Dispose()
    }

    if ((Get-Item -LiteralPath $source).Length -gt 50MB) {
        throw "Store screenshot exceeds 50 MB: $($entry.Key)"
    }

    Copy-Item -LiteralPath $source -Destination (Join-Path $screensDir $entry.Value)
}

Copy-Item -LiteralPath (Join-Path $repoRoot "docs\MICROSOFT_STORE_FIRST_SUBMISSION.md") -Destination $packDir

if ($PackagePath) {
    $resolvedPackage = Resolve-Path -LiteralPath $PackagePath
    if ([IO.Path]::GetExtension($resolvedPackage.Path) -ne ".msix") {
        throw "PackagePath must point to an MSIX file."
    }
    Copy-Item -LiteralPath $resolvedPackage.Path -Destination $packDir
}

$hashes = Get-ChildItem -LiteralPath $packDir -File -Recurse |
    Sort-Object FullName |
    ForEach-Object {
        $relative = [IO.Path]::GetRelativePath($packDir, $_.FullName).Replace('\', '/')
        $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        "$hash  $relative"
    }
$hashes | Set-Content -LiteralPath (Join-Path $packDir "SHA256SUMS.txt") -Encoding ascii

$zipPath = "$packDir.zip"
if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -Path (Join-Path $packDir "*") -DestinationPath $zipPath -CompressionLevel Optimal

Write-Host "Microsoft Store first-submission pack: $packDir"
Write-Host "Archive: $zipPath"
