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


def test_release_smokes_signed_gui_and_gates_live_auth_side_effects():
    workflow = Path(".github/workflows/build-release.yml").read_text(encoding="utf-8")
    packaged_smoke = Path("tools/packaged_gui_smoke.ps1").read_text(encoding="utf-8")

    assert "run_live_auth_smoke:" in workflow
    assert "default: false" in workflow
    assert "github.event_name == 'workflow_dispatch' && inputs.run_live_auth_smoke" in workflow
    assert 'tools\\live_auth_gui_smoke.ps1" -HoldSeconds 5' in workflow
    assert workflow.index("- name: Validate release version") < workflow.index(
        "- name: Run explicitly approved live authentication GUI smoke"
    )

    signature_index = workflow.index("- name: Verify executable release signature")
    gui_smoke_index = workflow.index("- name: Launch signed packaged login window")
    build_verification_index = workflow.index("- name: Verify build")
    assert signature_index < gui_smoke_index < build_verification_index

    assert 'THREAD_AUTO_DISABLE_AUTOSTART_SYNC = "1"' in packaged_smoke
    assert "$env:USERPROFILE = $smokeHome" in packaged_smoke
    assert "$env:LOCALAPPDATA = $localDir" in packaged_smoke
    assert 'MainWindowTitle -eq "스레드 쇼핑 자동화 - 로그인"' in packaged_smoke
    assert "$windowProcess.CloseMainWindow()" in packaged_smoke
    assert 'Get-CimInstance -ClassName Win32_Process' in packaged_smoke
    assert '-Filter "ParentProcessId = $currentId"' in packaged_smoke
    assert "$process.ExitCode -ne 0" in packaged_smoke
    assert "processes did not terminate during cleanup" in packaged_smoke
    assert "Refusing to remove GUI smoke data outside the temporary directory" in packaged_smoke

    live_smoke = Path("tools/live_auth_ui_smoke.py").read_text(encoding="utf-8")
    assert "atexit.register(_cleanup_live_smoke)" in live_smoke
    assert 'auth_client.remember_login_credentials("", "")' in live_smoke

    live_wrapper = Path("tools/live_auth_gui_smoke.ps1").read_text(encoding="utf-8")
    assert "$env:USERPROFILE = $smokeHome" in live_wrapper
    assert "$env:LOCALAPPDATA = $localDir" in live_wrapper
    assert "Refusing to remove live-auth smoke data outside the temporary directory" in live_wrapper


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
        "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
    ) in workflow
    assert "AZURE_AD_APPLICATION_SECRET: ${{ secrets.AZURE_AD_APPLICATION_SECRET }}" in workflow
    assert "STORE_PRODUCT_ID: ${{ vars.MS_STORE_PRODUCT_ID }}" in workflow
    assert "msstore publish" in workflow
