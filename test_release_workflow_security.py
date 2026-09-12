import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _job(workflow: str, name: str, next_name: str) -> str:
    return workflow.split(f"  {name}:\n", 1)[1].split(f"  {next_name}:\n", 1)[0]


def test_release_version_is_single_source_and_untrusted_inputs_stay_in_env():
    workflow = _read(".github/workflows/build-release.yml")
    version_job = workflow.split("- name: Validate canonical release version", 1)[1].split(
        "- name: Require exact managed signer pins", 1
    )[0]

    assert "RELEASE_VERSION_INPUT: ${{ inputs.version || '' }}" in version_job
    run_script = version_job.split("run: |", 1)[1]
    assert "${{ inputs.version" not in run_script
    assert "from src.version import VERSION_TAG" in run_script
    assert 'GITHUB_REF_NAME" != "$VERSION' in run_script
    assert "does not match src/version.py" in run_script
    assert "next_version.py" not in workflow
    assert "set_version.py" not in workflow
    assert "bump:" not in workflow
    assert "Require a protected release tag" in workflow
    assert "github.ref_type" in workflow
    assert "github.ref_protected" in workflow
    assert "Public signing and release require a protected canonical tag ref" in workflow


def test_managed_signing_jobs_are_oidc_isolated_pinned_and_fail_closed():
    workflow = _read(".github/workflows/build-release.yml")
    executable_signer = _job(workflow, "sign-executable", "build-installer")
    installer_signer = _job(workflow, "sign-installer", "verify-release")

    for signer in (executable_signer, installer_signer):
        assert "environment: production-code-signing" in signer
        assert "id-token: write" in signer
        assert "Managed signing is not configured" in signer
        assert "actions/checkout@" not in signer
        assert ".github/scripts" not in signer
        assert "WINDOWS_CODE_SIGN_CERT" not in signer
        assert "CERT_PASSWORD" not in signer
        assert "Exportable" not in signer
        assert (
            "azure/login@7ddb5af1ef8758cf1353cf3b42f940aee27ba21c"
            in signer
        )
        assert (
            "azure/artifact-signing-action@c7ab2a863ab5f9a846ddb8265964877ef296ee82"
            in signer
        )
        assert "exclude-environment-credential: true" in signer
        assert "exclude-azure-cli-credential: false" in signer

    uses = re.findall(r"^\s*uses:\s*([^\s#]+)", workflow, re.MULTILINE)
    assert uses
    assert all(re.fullmatch(r"[^@]+@[0-9a-f]{40}", action) for action in uses)
    assert not (ROOT / ".github/scripts/sign-windows-artifact.ps1").exists()


def test_exact_detached_verification_requires_public_non_revoked_timestamped_chain():
    verifier = _read(".github/scripts/assert-public-authenticode.ps1")

    assert "TrustedThumbprints" in verifier
    assert "one pin, or current,next" in verifier
    assert "SignatureStatus]::Valid" in verifier
    assert "X509RevocationMode]::Online" in verifier
    assert "X509RevocationFlag]::EntireChain" in verifier
    assert "X509VerificationFlags]::NoFlag" in verifier
    assert "ApplicationPolicy" in verifier
    assert "1.3.6.1.5.5.7.3.8" in verifier
    assert "Code Signing EKU" in verifier
    assert "TimeStamperCertificate" in verifier
    assert "NotTrusted" not in verifier
    assert "UnknownError" not in verifier
    assert "AllowPinnedSelfSigned" not in verifier
    assert "NoCheck" not in verifier
    assert "IgnoreNotTimeValid" not in verifier


def test_release_uses_signed_inner_exe_and_promotes_only_verified_artifacts():
    workflow = _read(".github/workflows/build-release.yml")
    assert workflow.index("  build-executable:") < workflow.index("  sign-executable:")
    assert workflow.index("  sign-executable:") < workflow.index("  build-installer:")
    assert workflow.index("  build-installer:") < workflow.index("  sign-installer:")
    assert workflow.index("  sign-installer:") < workflow.index("  verify-release:")
    assert workflow.index("  verify-release:") < workflow.index("  release:")

    installer_builder = _job(workflow, "build-installer", "sign-installer")
    assert "Download verified signed executable" in installer_builder
    assert installer_builder.index("assert-public-authenticode.ps1") < installer_builder.index(
        "python build_installer.py"
    )

    installer_signer = _job(workflow, "sign-installer", "verify-release")
    assert "Download immutable original signed executable" in installer_signer
    assert "signed-executable-${{ needs.build-installer.outputs.version }}" in installer_signer
    assert "Signed executable was replaced by the installer build stage" in installer_signer
    assert installer_signer.index("Reject signed executable substitution") < installer_signer.index(
        "Sign installer with Azure Artifact Signing"
    )

    verifier = _job(workflow, "verify-release", "release")
    assert "Install, launch, and uninstall the final installer" in verifier
    assert "Installer payload does not match the verified standalone executable" in verifier
    install_step = verifier.split("- name: Install, launch, and uninstall the final installer", 1)[1]
    assert install_step.index("assert-public-authenticode.ps1") < install_step.index(
        "packaged_gui_smoke.ps1"
    )
    assert "unins000.exe" in verifier
    assert "Promote only verified signed artifacts" in verifier

    release = workflow.split("  release:\n", 1)[1]
    assert "needs: verify-release" in release
    assert "verified-release-${{ needs.verify-release.outputs.version }}" in release
    assert "signed-release-${{" not in release


def test_release_smokes_gui_and_live_auth_remains_explicitly_gated():
    workflow = _read(".github/workflows/build-release.yml")
    packaged_smoke = _read("tools/packaged_gui_smoke.ps1")

    assert "run_live_auth_smoke:" in workflow
    assert "default: false" in workflow
    assert "github.event_name == 'workflow_dispatch' && inputs.run_live_auth_smoke" in workflow
    assert 'tools\\live_auth_gui_smoke.ps1" -HoldSeconds 5' in workflow
    canary_job = workflow.split("  live-auth-canary:\n", 1)[1].split(
        "  sign-executable:\n", 1
    )[0]
    assert "needs: build-executable" in canary_job
    assert "environment: production-live-auth-canary" in canary_job
    assert "pip install --require-hashes -r requirements.lock" in canary_job
    sign_job = workflow.split("  sign-executable:\n", 1)[1].split(
        "  build-installer:\n", 1
    )[0]
    assert "needs: [build-executable, live-auth-canary]" in sign_job
    assert "needs.live-auth-canary.result == 'success'" in sign_job
    assert "needs.live-auth-canary.result == 'skipped'" in sign_job
    assert workflow.index("- name: Validate canonical release version") < workflow.index(
        "- name: Run explicitly approved live authentication GUI smoke"
    )
    assert workflow.count("tools\\packaged_gui_smoke.ps1") >= 2

    assert 'THREAD_AUTO_DISABLE_AUTOSTART_SYNC = "1"' in packaged_smoke
    assert "$env:USERPROFILE = $smokeHome" in packaged_smoke
    assert "$env:LOCALAPPDATA = $localDir" in packaged_smoke
    assert '[Convert]::FromBase64String(' in packaged_smoke
    assert "MainWindowTitle -eq $expectedWindowTitle" in packaged_smoke
    assert packaged_smoke.isascii(), "Windows PowerShell 5 requires an ASCII-safe script"
    assert "Refusing to remove GUI smoke data outside the temporary directory" in packaged_smoke


def test_free_store_workflow_is_manual_pinned_and_version_locked():
    workflow = _read(".github/workflows/store-release.yml")
    build_job = workflow.split("  build-store-package:\n", 1)[1].split(
        "  publish-store-package:\n", 1
    )[0]
    publish_job = workflow.split("  publish-store-package:\n", 1)[1]

    assert "workflow_dispatch:" in workflow
    assert "publish:" in workflow
    assert "tools/build_store_msix.py" in workflow
    assert "validate_store_version" in workflow
    assert "read_app_version(Path('.'))" in workflow
    assert "YMcompany.30069A065C875" in workflow
    assert "SSLcom" not in workflow
    assert "ESIGNER_" not in workflow
    assert (
        "microsoft/microsoft-store-apppublisher@"
        "15abd1c50fcc164b19cb240fb04ef3c49bf715a2"
    ) in workflow
    assert "STORE_PRODUCT_ID: ${{ vars.MS_STORE_PRODUCT_ID }}" in workflow
    assert "msstore publish" in workflow
    assert "AZURE_AD_APPLICATION_SECRET" not in build_job
    assert "environment: production-store-publishing" in publish_job
    assert "actions/checkout@" not in publish_job
    assert "Download the package built by this workflow run" in publish_job
    assert "Store package checksum mismatch" in publish_job
    assert "Unexpected Store package identity" in publish_job
    assert "Microsoft Store publication requires a protected branch or tag ref" in build_job
    assert "actions/setup-node@820762786026740c76f36085b0efc47a31fe5020" in workflow
    assert 'node-version: "22"' in workflow
    assert workflow.index("npm ci") < workflow.index("node --test tests_js/*.test.mjs")


def test_branch_ci_covers_master_and_codex_with_locked_checks():
    workflow = _read(".github/workflows/ci.yml")

    assert "- master" in workflow
    assert '- "codex/**"' in workflow
    assert "pip install --require-hashes -r requirements.lock" in workflow
    assert "npm ci" in workflow
    assert "python -m pytest -q" in workflow
    assert "python -m compileall -q main.py login_main.py setup_login.py src" in workflow
    assert "python tools/sanity_check.py" in workflow
    assert "npm test" in workflow
    assert "npm audit --omit=dev" in workflow
