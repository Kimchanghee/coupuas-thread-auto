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
  Set-AuthenticodeSignature -FilePath $Path -Certificate $cert -HashAlgorithm SHA256 | Out-Null

  $signature = Get-AuthenticodeSignature -FilePath $Path
  if (-not $signature.SignerCertificate) {
    throw "Artifact was not signed: $Path"
  }

  $actualThumbprint = Normalize-Thumbprint $signature.SignerCertificate.Thumbprint
  if ($actualThumbprint -ne $expectedThumbprint) {
    throw "Signed artifact thumbprint mismatch. Expected $expectedThumbprint, got $actualThumbprint."
  }

  if ($signature.Status -eq [System.Management.Automation.SignatureStatus]::HashMismatch) {
    throw "Signed artifact hash mismatch: $Path"
  }

  $status = $signature.Status.ToString()

  if ($status -eq "Valid") {
    Write-Host "Signature status: $status"
  } elseif ($status -eq "NotTrusted" -or $status -eq "UnknownError") {
    $message = $signature.StatusMessage
    $isTrustChainOnly =
      $message -match "(?i)not trusted" -or
      $message -match "(?i)root certificate" -or
      $message -match "(?i)trust provider" -or
      $message -match "(?i)certificate chain"

    if (-not $isTrustChainOnly) {
      throw "Unexpected Authenticode trust status for ${Path}: $status - $message"
    }

    Write-Host "Signature status: $status"
  } else {
    throw "Unexpected Authenticode status for ${Path}: $status - $($signature.StatusMessage)"
  }

  if (-not [string]::IsNullOrWhiteSpace($signature.StatusMessage)) {
    Write-Host "Signature message: $($signature.StatusMessage)"
  }
} finally {
  Remove-Item -LiteralPath $certPath -Force -ErrorAction SilentlyContinue
}
