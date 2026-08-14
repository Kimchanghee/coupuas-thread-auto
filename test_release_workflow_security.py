from pathlib import Path


def test_release_inputs_reach_shell_only_through_environment():
    workflow = Path(".github/workflows/build-release.yml").read_text(encoding="utf-8")
    get_version = workflow.split("- name: Get version", 1)[1].split(
        "- name: Validate release version", 1
    )[0]

    assert "RELEASE_VERSION_INPUT: ${{ inputs.version || '' }}" in get_version
    assert "RELEASE_BUMP_INPUT: ${{ inputs.bump || 'patch' }}" in get_version
    run_script = get_version.split("run: |", 1)[1]
    assert "${{ inputs.version" not in run_script
    assert "${{ inputs.bump" not in run_script
    assert 'Invalid explicit version format' in run_script


def test_release_requires_publicly_trusted_timestamped_authenticode():
    workflow = Path(".github/workflows/build-release.yml").read_text(encoding="utf-8")
    verifier = Path(".github/scripts/assert-public-authenticode.ps1").read_text(
        encoding="utf-8"
    )
    signer = Path(".github/scripts/sign-windows-artifact.ps1").read_text(
        encoding="utf-8"
    )

    pinned_esigner = (
        "SSLcom/esigner-codesign@"
        "cf5f6c1d38ad10f47e3ed9aca873f429b1a8d85b"
    )
    assert workflow.count(pinned_esigner) == 2
    assert "SSLcom/esigner-codesign@develop" not in workflow
    assert workflow.count("assert-public-authenticode.ps1") == 2
    assert "ESIGNER_CREDENTIAL_ID" in workflow
    assert "ESIGNER_TOTP_SECRET" in workflow

    assert "SignatureStatus]::Valid" in verifier
    assert "X509Chain]::new()" in verifier
    assert "TimeStamperCertificate" in verifier
    assert "Code Signing EKU" in verifier
    assert "self-signed" in verifier
    assert "NotTrusted" not in signer
    assert "UnknownError" not in signer
    assert '-TimestampServer "http://ts.ssl.com"' in signer
