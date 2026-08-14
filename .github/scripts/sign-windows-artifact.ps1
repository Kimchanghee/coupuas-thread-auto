param(
  [Parameter(Mandatory = $true)]
  [string]$Path
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RequiredEnv {
  param([Parameter(Mandatory = $true)][string]$Name)

  $value = [Environment]::GetEnvironmentVariable($Name)
  if ([string]::IsNullOrWhiteSpace($value)) {
    throw "$Name is required for release signing."
  }
  return $value
}

function Normalize-Thumbprint {
  param([Parameter(Mandatory = $true)][string]$Value)

  return ($Value -replace "\s", "").ToUpperInvariant()
}

$certBase64 = Get-RequiredEnv "WINDOWS_CODE_SIGN_CERT_BASE64"
$certPassword = Get-RequiredEnv "WINDOWS_CODE_SIGN_CERT_PASSWORD"
$expectedThumbprint = Normalize-Thumbprint (Get-RequiredEnv "CODE_SIGN_CERT_THUMBPRINT")

if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
  throw "Artifact not found: $Path"
}

$certPath = Join-Path $env:RUNNER_TEMP ("codesign-{0}.pfx" -f [Guid]::NewGuid())

try {
  [IO.File]::WriteAllBytes($certPath, [Convert]::FromBase64String($certBase64))

  $flags = [System.Security.Cryptography.X509Certificates.X509KeyStorageFlags]::Exportable -bor
    [System.Security.Cryptography.X509Certificates.X509KeyStorageFlags]::MachineKeySet
  $cert = [System.Security.Cryptography.X509Certificates.X509Certificate2]::new($certPath, $certPassword, $flags)

  if (-not $cert.HasPrivateKey) {
    throw "Signing certificate does not include a private key."
  }

  $loadedThumbprint = Normalize-Thumbprint $cert.Thumbprint
  if ($loadedThumbprint -ne $expectedThumbprint) {
    throw "Signing certificate thumbprint mismatch. Expected $expectedThumbprint, got $loadedThumbprint."
  }

  Write-Host "Signing $Path with pinned certificate $expectedThumbprint"
  Set-AuthenticodeSignature `
    -FilePath $Path `
    -Certificate $cert `
    -HashAlgorithm SHA256 `
    -TimestampServer "http://timestamp.digicert.com" | Out-Null

  $signature = Get-AuthenticodeSignature -FilePath $Path
  if (-not $signature.SignerCertificate) {
    throw "Artifact was not signed: $Path"
  }

  $actualThumbprint = Normalize-Thumbprint $signature.SignerCertificate.Thumbprint
  if ($actualThumbprint -ne $expectedThumbprint) {
    throw "Signed artifact thumbprint mismatch. Expected $expectedThumbprint, got $actualThumbprint."
  }

  & (Join-Path $PSScriptRoot "assert-public-authenticode.ps1") `
    -Path $Path `
    -ExpectedThumbprint $expectedThumbprint
} finally {
  Remove-Item -LiteralPath $certPath -Force -ErrorAction SilentlyContinue
}
