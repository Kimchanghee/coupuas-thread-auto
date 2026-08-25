param(
  [Parameter(Mandatory = $true)]
  [string]$Path,

  [Parameter(Mandatory = $true)]
  [string]$ExpectedThumbprint,

  [switch]$AllowPinnedSelfSigned
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($AllowPinnedSelfSigned -and $env:GITHUB_ACTIONS -eq "true") {
  throw "AllowPinnedSelfSigned is restricted to explicit local development use."
}

function Normalize-Thumbprint {
  param([Parameter(Mandatory = $true)][string]$Value)

  return ($Value -replace "\s", "").ToUpperInvariant()
}

function Assert-TrustedChain {
  param(
    [Parameter(Mandatory = $true)]
    [System.Security.Cryptography.X509Certificates.X509Certificate2]$Certificate,

    [Parameter(Mandatory = $true)]
    [string]$Description
  )

  $chain = [System.Security.Cryptography.X509Certificates.X509Chain]::new()
  try {
    $chain.ChainPolicy.RevocationMode =
      [System.Security.Cryptography.X509Certificates.X509RevocationMode]::Online
    $chain.ChainPolicy.RevocationFlag =
      [System.Security.Cryptography.X509Certificates.X509RevocationFlag]::ExcludeRoot
    # Get-AuthenticodeSignature already validates certificate time at the trusted
    # timestamp. Ignore current-time expiry here while still requiring a trusted,
    # non-revoked public chain.
    $chain.ChainPolicy.VerificationFlags =
      [System.Security.Cryptography.X509Certificates.X509VerificationFlags]::IgnoreNotTimeValid
    $chain.ChainPolicy.UrlRetrievalTimeout = [TimeSpan]::FromSeconds(20)

    if (-not $chain.Build($Certificate)) {
      $details = ($chain.ChainStatus | ForEach-Object {
          "{0}: {1}" -f $_.Status, $_.StatusInformation.Trim()
        }) -join "; "
      throw "$Description certificate does not chain to a publicly trusted root: $details"
    }

    $root = $chain.ChainElements[$chain.ChainElements.Count - 1].Certificate
    if ($root.Thumbprint -eq $Certificate.Thumbprint) {
      throw "$Description certificate is self-signed and is not acceptable for a public release."
    }
  } finally {
    $chain.Dispose()
  }
}

function Assert-PinnedSelfSignedChain {
  param(
    [Parameter(Mandatory = $true)]
    [System.Security.Cryptography.X509Certificates.X509Certificate2]$Certificate
  )

  if ($Certificate.Subject -ne $Certificate.Issuer) {
    throw "Pinned fallback signer must be self-signed."
  }

  $chain = [System.Security.Cryptography.X509Certificates.X509Chain]::new()
  try {
    $chain.ChainPolicy.RevocationMode =
      [System.Security.Cryptography.X509Certificates.X509RevocationMode]::NoCheck
    $chain.ChainPolicy.VerificationFlags =
      [System.Security.Cryptography.X509Certificates.X509VerificationFlags]::NoFlag
    $built = $chain.Build($Certificate)
    $statuses = @($chain.ChainStatus | ForEach-Object { $_.Status.ToString() })
    $unexpected = @($statuses | Where-Object { $_ -ne "UntrustedRoot" })
    if ($built -or $statuses.Count -eq 0 -or $unexpected.Count -gt 0) {
      throw "Pinned fallback signer has an unexpected certificate state: $($statuses -join ', ')"
    }
    if ($chain.ChainElements.Count -ne 1) {
      throw "Pinned fallback signer must have a one-certificate chain."
    }
  } finally {
    $chain.Dispose()
  }
}

if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
  throw "Artifact not found: $Path"
}

$signature = Get-AuthenticodeSignature -FilePath $Path
if (-not $signature.SignerCertificate) {
  throw "Artifact has no signer certificate: $Path"
}

$isPubliclyTrusted =
  $signature.Status -eq [System.Management.Automation.SignatureStatus]::Valid
if (-not $isPubliclyTrusted) {
  $allowedPinnedStatus =
    $signature.Status -eq [System.Management.Automation.SignatureStatus]::NotTrusted -or
    $signature.Status -eq [System.Management.Automation.SignatureStatus]::UnknownError
  if (-not $AllowPinnedSelfSigned -or -not $allowedPinnedStatus) {
    throw "Public Authenticode validation failed for ${Path}: $($signature.Status) - $($signature.StatusMessage)"
  }
}

$expected = Normalize-Thumbprint $ExpectedThumbprint
$actual = Normalize-Thumbprint $signature.SignerCertificate.Thumbprint
if ($actual -ne $expected) {
  throw "Signed artifact thumbprint mismatch. Expected $expected, got $actual."
}

$codeSigningOid = "1.3.6.1.5.5.7.3.3"
$hasCodeSigningEku = $signature.SignerCertificate.Extensions |
  Where-Object { $_ -is [System.Security.Cryptography.X509Certificates.X509EnhancedKeyUsageExtension] } |
  ForEach-Object { $_.EnhancedKeyUsages } |
  Where-Object { $_.Value -eq $codeSigningOid }
if (-not $hasCodeSigningEku) {
  throw "Signer certificate is missing the Code Signing EKU: $actual"
}

if ($isPubliclyTrusted) {
  Assert-TrustedChain -Certificate $signature.SignerCertificate -Description "Signer"
} else {
  Assert-PinnedSelfSignedChain -Certificate $signature.SignerCertificate
}

if (-not $signature.TimeStamperCertificate) {
  throw "Artifact is not timestamped: $Path"
}
Assert-TrustedChain -Certificate $signature.TimeStamperCertificate -Description "Timestamp"

Write-Host "Release Authenticode signature verified: $Path"
Write-Host "Signer: $($signature.SignerCertificate.Subject)"
Write-Host "Thumbprint: $actual"
Write-Host "Timestamp authority: $($signature.TimeStamperCertificate.Subject)"
