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
