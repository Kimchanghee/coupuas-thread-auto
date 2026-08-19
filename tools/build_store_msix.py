"""Build helpers for the Microsoft Store MSIX distribution."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import build_exe  # noqa: E402 - repository root must be added before import


PACKAGE_IDENTITY_NAME = "YMcompany.30069A065C875"
PACKAGE_PUBLISHER = "CN=447AAE61-8C19-4267-91D6-45419445A405"
PUBLISHER_DISPLAY_NAME = "YMcompany"
PRODUCT_DISPLAY_NAME = "스레드 쇼핑 자동화"
EXECUTABLE_NAME = "CoupangThreadAuto.exe"


def normalize_msix_version(value: str) -> str:
    """Convert the app version to the four-part numeric MSIX format."""
    text = str(value or "").strip().lstrip("v")
    parts = text.split(".") if text else []
    if len(parts) == 3:
        parts.append("0")
    if len(parts) != 4 or any(not re.fullmatch(r"\d+", part) for part in parts):
        raise ValueError(f"Invalid MSIX version: {value!r}")
    numbers = [int(part) for part in parts]
    if any(number > 65535 for number in numbers):
        raise ValueError(f"MSIX version component exceeds 65535: {value!r}")
    return ".".join(str(number) for number in numbers)


def read_app_version(entrypoint_path: Path) -> str:
    """Read and normalize VERSION from a Python entrypoint."""
    source = Path(entrypoint_path).read_text(encoding="utf-8")
    match = re.search(r'^VERSION\s*=\s*["\']([^"\']+)["\']', source, re.MULTILINE)
    if not match:
        raise ValueError(f"VERSION was not found in {entrypoint_path}")
    return normalize_msix_version(match.group(1))


def build_manifest(version: str) -> str:
    """Return the Store-associated manifest for the packaged desktop app."""
    return f"""<?xml version="1.0" encoding="utf-8"?>
<Package
  xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
  xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"
  xmlns:uap10="http://schemas.microsoft.com/appx/manifest/uap/windows10/10"
  xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities"
  IgnorableNamespaces="uap uap10 rescap">
  <Identity
    Name="{PACKAGE_IDENTITY_NAME}"
    Publisher="{PACKAGE_PUBLISHER}"
    Version="{version}"
    ProcessorArchitecture="x64" />
  <Properties>
    <DisplayName>{PRODUCT_DISPLAY_NAME}</DisplayName>
    <PublisherDisplayName>{PUBLISHER_DISPLAY_NAME}</PublisherDisplayName>
    <Description>여러 쇼핑몰 상품 링크를 분석해 Threads 콘텐츠 작성을 돕는 자동화 도구</Description>
    <Logo>Assets\\StoreLogo.png</Logo>
  </Properties>
  <Resources>
    <Resource Language="ko-kr" />
  </Resources>
  <Dependencies>
    <TargetDeviceFamily
      Name="Windows.Desktop"
      MinVersion="10.0.19041.0"
      MaxVersionTested="10.0.26100.0" />
  </Dependencies>
  <Capabilities>
    <rescap:Capability Name="runFullTrust" />
  </Capabilities>
  <Applications>
    <Application
      Id="ThreadShoppingAutomation"
      Executable="{EXECUTABLE_NAME}"
      uap10:RuntimeBehavior="packagedClassicApp"
      uap10:TrustLevel="mediumIL">
      <uap:VisualElements
        DisplayName="{PRODUCT_DISPLAY_NAME}"
        Description="여러 쇼핑몰 상품 링크를 분석해 Threads 콘텐츠 작성을 돕는 자동화 도구"
        BackgroundColor="transparent"
        Square150x150Logo="Assets\\Square150x150Logo.png"
        Square44x44Logo="Assets\\Square44x44Logo.png" />
    </Application>
  </Applications>
</Package>
"""


def prepare_package_layout(
    *,
    executable_path: Path,
    staging_dir: Path,
    icon_path: Path,
    version: str,
) -> None:
    """Create the directory tree consumed by MakeAppx."""
    executable_path = Path(executable_path)
    staging_dir = Path(staging_dir)
    icon_path = Path(icon_path)
    if not executable_path.is_file():
        raise FileNotFoundError(executable_path)
    if not icon_path.is_file():
        raise FileNotFoundError(icon_path)

    assets_dir = staging_dir / "Assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(executable_path, staging_dir / EXECUTABLE_NAME)
    (staging_dir / "AppxManifest.xml").write_text(
        build_manifest(normalize_msix_version(version)),
        encoding="utf-8",
    )

    asset_sizes = {
        "StoreLogo.png": (50, 50),
        "Square44x44Logo.png": (44, 44),
        "Square150x150Logo.png": (150, 150),
    }
    with Image.open(icon_path) as source:
        rgba_source = source.convert("RGBA")
        for filename, size in asset_sizes.items():
            resized = rgba_source.resize(size, Image.Resampling.LANCZOS)
            resized.save(assets_dir / filename, format="PNG", optimize=True)


def build_pyinstaller_command(
    *,
    repo_root: Path,
    work_dir: Path,
    dist_dir: Path,
) -> list[str]:
    """Build the PyInstaller command without touching normal release artifacts."""
    repo_root = Path(repo_root).resolve()
    work_dir = Path(work_dir).resolve()
    dist_dir = Path(dist_dir).resolve()
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        "CoupangThreadAuto",
        "--onefile",
        "--windowed",
        "--clean",
        "--noconfirm",
        "--noupx",
        "--optimize",
        "2",
        "--workpath",
        str(work_dir),
        "--distpath",
        str(dist_dir),
        "--specpath",
        str(work_dir),
    ]

    icon_path = repo_root / "images" / "app_icon.ico"
    if icon_path.is_file():
        command.extend(["--icon", str(icon_path)])
    for hidden_import in build_exe.HIDDEN_IMPORTS:
        command.extend(["--hidden-import", hidden_import])
    for source, destination in build_exe.DATAS:
        source_path = (repo_root / source).resolve()
        if source_path.exists():
            command.extend(["--add-data", f"{source_path};{destination}"])
    for excluded_module in build_exe.EXCLUDES:
        command.extend(["--exclude-module", excluded_module])

    playwright_driver = build_exe.get_playwright_driver_path()
    if playwright_driver:
        command.extend(["--add-data", f"{playwright_driver};playwright/driver"])
    command.append(str((repo_root / "login_main.py").resolve()))
    return command


def find_makeappx(search_roots: list[Path]) -> Path:
    """Locate the newest available x64 MakeAppx tool under known SDK roots."""
    candidates: list[Path] = []
    for root in search_roots:
        root_path = Path(root)
        if root_path.exists():
            candidates.extend(path for path in root_path.rglob("makeappx.exe") if path.is_file())
    x64_candidates = [path for path in candidates if path.parent.name.lower() == "x64"]
    preferred = x64_candidates or candidates
    if not preferred:
        raise FileNotFoundError("MakeAppx.exe was not found")
    return sorted(preferred, key=lambda path: str(path), reverse=True)[0]


def build_store_package(
    *,
    repo_root: Path,
    makeappx_path: Path,
    build_root: Path,
    output_dir: Path,
    version: str,
) -> Path:
    """Build the frozen desktop executable and wrap it in an unsigned Store MSIX."""
    repo_root = Path(repo_root).resolve()
    makeappx_path = Path(makeappx_path).resolve()
    build_root = Path(build_root).resolve()
    output_dir = Path(output_dir).resolve()
    if not makeappx_path.is_file():
        raise FileNotFoundError(makeappx_path)

    msix_version = normalize_msix_version(version)
    build_root.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    work_dir = Path(tempfile.mkdtemp(prefix="pyinstaller-", dir=build_root))
    executable_dir = Path(tempfile.mkdtemp(prefix="executable-", dir=build_root))
    staging_dir = Path(tempfile.mkdtemp(prefix="msix-staging-", dir=build_root))

    pyinstaller_command = build_pyinstaller_command(
        repo_root=repo_root,
        work_dir=work_dir,
        dist_dir=executable_dir,
    )
    subprocess.run(pyinstaller_command, cwd=repo_root, check=True)
    executable_path = executable_dir / EXECUTABLE_NAME
    if not executable_path.is_file():
        raise FileNotFoundError(f"PyInstaller output is missing: {executable_path}")

    prepare_package_layout(
        executable_path=executable_path,
        staging_dir=staging_dir,
        icon_path=repo_root / "images" / "app_icon.ico",
        version=msix_version,
    )
    output_path = output_dir / f"ThreadShoppingAutomation_{msix_version}_x64.msix"
    subprocess.run(
        [
            str(makeappx_path),
            "pack",
            "/d",
            str(staging_dir),
            "/p",
            str(output_path),
            "/o",
        ],
        cwd=repo_root,
        check=True,
    )
    if not output_path.is_file():
        raise FileNotFoundError(f"MakeAppx output is missing: {output_path}")
    return output_path


def main(argv: list[str] | None = None, *, repo_root: Path | None = None) -> int:
    """Command-line entrypoint for creating the Partner Center upload package."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--makeappx", type=Path, help="Path to makeappx.exe")
    parser.add_argument("--output-dir", type=Path, help="MSIX output directory")
    parser.add_argument("--build-root", type=Path, help="Temporary build directory")
    parser.add_argument(
        "--version",
        help="MSIX version override (three or four numeric parts, optional leading v)",
    )
    args = parser.parse_args(argv)

    resolved_repo_root = (
        Path(repo_root).resolve()
        if repo_root is not None
        else Path(__file__).resolve().parents[1]
    )
    version = (
        normalize_msix_version(args.version)
        if args.version
        else read_app_version(resolved_repo_root / "login_main.py")
    )
    if args.makeappx:
        makeappx_path = args.makeappx.resolve()
    else:
        program_files_x86 = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
        makeappx_path = find_makeappx(
            [
                resolved_repo_root / "build" / "store-sdk",
                program_files_x86 / "Windows Kits" / "10",
            ]
        )

    output_path = build_store_package(
        repo_root=resolved_repo_root,
        makeappx_path=makeappx_path,
        build_root=(args.build_root or resolved_repo_root / "build" / "store").resolve(),
        output_dir=(args.output_dir or resolved_repo_root / "dist" / "store").resolve(),
        version=version,
    )
    print(f"Microsoft Store MSIX created: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
