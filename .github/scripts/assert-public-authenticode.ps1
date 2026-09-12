param(
  [Parameter(Mandatory = $true)]
  [string]$Path,

  [Parameter(Mandatory = $true)]
  [string]$TrustedThumbprints
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function ConvertTo-TrustedThumbprintSet {
  param([Parameter(Mandatory = $true)][string]$Value)

  $pins = @(
    $Value -split "[,;\s]+" |
      Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
      ForEach-Object {
        $normalized = ($_ -replace "[^a-fA-F0-9]", "").ToUpperInvariant()
        if ($normalized -notmatch "^[A-F0-9]{40}$") {
          throw "Invalid SHA-1 certificate thumbprint: $_"
        }
        $normalized
      } |
      Select-Object -Unique
  )
  if ($pins.Count -lt 1 -or $pins.Count -gt 2) {
    throw "TrustedThumbprints must contain one pin, or current,next during rotation."
  }
  return $pins
}

function Assert-TrustedChain {
  param(
    [Parameter(Mandatory = $true)]
    [System.Security.Cryptography.X509Certificates.X509Certificate2]$Certificate,

    [Parameter(Mandatory = $true)]
    [string]$Description,

    [Parameter(Mandatory = $true)]
    [string]$ApplicationPolicyOid
  )

  $chain = [System.Security.Cryptography.X509Certificates.X509Chain]::new()
  try {
    $chain.ChainPolicy.RevocationMode =
      [System.Security.Cryptography.X509Certificates.X509RevocationMode]::Online
    $chain.ChainPolicy.RevocationFlag =
      [System.Security.Cryptography.X509Certificates.X509RevocationFlag]::EntireChain
    $chain.ChainPolicy.VerificationFlags =
      [System.Security.Cryptography.X509Certificates.X509VerificationFlags]::NoFlag
    $chain.ChainPolicy.UrlRetrievalTimeout = [TimeSpan]::FromSeconds(20)
    [void]$chain.ChainPolicy.ApplicationPolicy.Add(
      [System.Security.Cryptography.Oid]::new($ApplicationPolicyOid)
    )

    if (-not $chain.Build($Certificate)) {
      $details = ($chain.ChainStatus | ForEach-Object {
          "{0}: {1}" -f $_.Status, $_.StatusInformation.Trim()
        }) -join "; "
      throw "$Description certificate does not chain to a non-revoked public root: $details"
    }
    $root = $chain.ChainElements[$chain.ChainElements.Count - 1].Certificate
    if ($root.Thumbprint -eq $Certificate.Thumbprint) {
      throw "$Description certificate must not be self-signed."
    }
  } finally {
    $chain.Dispose()
  }
}

if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
  throw "Artifact not found: $Path"
}

$trusted = ConvertTo-TrustedThumbprintSet -Value $TrustedThumbprints
$signature = Get-AuthenticodeSignature -FilePath $Path
if ($signature.Status -ne [System.Management.Automation.SignatureStatus]::Valid) {
  throw "Public Authenticode validation failed for ${Path}: $($signature.Status) - $($signature.StatusMessage)"
}
if (-not $signature.SignerCertificate) {
  throw "Artifact has no signer certificate: $Path"
}

$actual = ($signature.SignerCertificate.Thumbprint -replace "[^a-fA-F0-9]", "").ToUpperInvariant()
if ($actual -notin $trusted) {
  throw "Signed artifact thumbprint is not pinned. Allowed: $($trusted -join ', '); got $actual."
}

$codeSigningOid = "1.3.6.1.5.5.7.3.3"
$hasCodeSigningEku = $signature.SignerCertificate.Extensions |
  Where-Object { $_ -is [System.Security.Cryptography.X509Certificates.X509EnhancedKeyUsageExtension] } |
  ForEach-Object { $_.EnhancedKeyUsages } |
  Where-Object { $_.Value -eq $codeSigningOid }
if (-not $hasCodeSigningEku) {
  throw "Signer certificate is missing the Code Signing EKU: $actual"
}

Assert-TrustedChain `
  -Certificate $signature.SignerCertificate `
  -Description "Signer" `
  -ApplicationPolicyOid $codeSigningOid
if (-not $signature.TimeStamperCertificate) {
  throw "Artifact is not timestamped: $Path"
}
Assert-TrustedChain `
  -Certificate $signature.TimeStamperCertificate `
  -Description "Timestamp" `
  -ApplicationPolicyOid "1.3.6.1.5.5.7.3.8"

Write-Host "Release Authenticode signature verified: $Path"
Write-Host "Signer: $($signature.SignerCertificate.Subject)"
Write-Host "Thumbprint: $actual"
Write-Host "Timestamp authority: $($signature.TimeStamperCertificate.Subject)"
