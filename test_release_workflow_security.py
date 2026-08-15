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


def test_release_requires_timestamped_authenticode_with_an_exact_signer_pin():
    workflow = Path(".github/workflows/build-release.yml").read_text(encoding="utf-8")
    verifier = Path(".github/scripts/assert-public-authenticode.ps1").read_text(
        encoding="utf-8"
    )
    signer = Path(".github/scripts/sign-windows-artifact.ps1").read_text(
        encoding="utf-8"
    )

    assert "SSLcom/esigner-codesign" not in workflow
    assert "ESIGNER_" not in workflow
    assert workflow.count("assert-public-authenticode.ps1") == 2
    assert workflow.count("-AllowPinnedSelfSigned") == 4
    assert "branches:" not in workflow.split("workflow_dispatch:", 1)[0]

    assert "SignatureStatus]::Valid" in verifier
    assert "X509Chain]::new()" in verifier
    assert "TimeStamperCertificate" in verifier
    assert "Code Signing EKU" in verifier
    assert "self-signed" in verifier
    assert "Assert-PinnedSelfSignedChain" in verifier
    assert '$_ -ne "UntrustedRoot"' in verifier
    assert "TimeStamperCertificate" in verifier
    assert "NotTrusted" not in signer
    assert "UnknownError" not in signer
    assert '-TimestampServer "http://timestamp.digicert.com"' in signer


def test_free_store_workflow_is_manual_pinned_and_payment_provider_free():
    workflow = Path(".github/workflows/store-release.yml").read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "publish:" in workflow
    assert "tools/build_store_msix.py" in workflow
    assert "makeappx.exe" in workflow
    assert "YMcompany.30069A065C875" in workflow
    assert "SSLcom" not in workflow
    assert "ESIGNER_" not in workflow
    assert (
        "microsoft/microsoft-store-apppublisher@"
        "15abd1c50fcc164b19cb240fb04ef3c49bf715a2"
    ) in workflow
    assert (
        "actions/upload-artifact@"
        "ea165f8d65b6e75b540449e92b4886f43607fa02"
    ) in workflow
    assert "AZURE_AD_APPLICATION_SECRET: ${{ secrets.AZURE_AD_APPLICATION_SECRET }}" in workflow
    assert "STORE_PRODUCT_ID: ${{ vars.MS_STORE_PRODUCT_ID }}" in workflow
    assert "msstore publish" in workflow
