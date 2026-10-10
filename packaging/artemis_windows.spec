# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller one-file Windows CLI. Run from the repository root after npm build.

The Python environment is provisioned with uv; users of the .exe need no Python
or uv installation. Android/ADB, an emulator/device, and API keys are external.
"""

from pathlib import Path
from importlib.metadata import PackageNotFoundError
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

root = Path.cwd()
if not (root / "pyproject.toml").is_file():
    raise RuntimeError("Run PyInstaller from the Artemis repository root.")

frontend = next(
    (
        p
        for p in (
            root / "apps/showcase_ui/dist/frontend/browser",
            root / "apps/showcase_ui/dist/browser",
            root / "apps/showcase_ui/dist/frontend",
            root / "apps/showcase_ui/dist",
        )
        if (p / "index.html").is_file()
    ),
    None,
)
if frontend is None:
    raise RuntimeError("Production UI missing; run npm ci and npm run build in apps/showcase_ui.")

datas = collect_data_files(
    "artemis",
    includes=["**/*.json", "**/*.jsonc", "**/*.md", "**/*.html", "**/*.js",
              "**/*.css", "**/*.png", "**/*.svg", "**/*.ico"],
    excludes=["resources/showcase_ui/**", "resources/config/**"],
)
datas += collect_data_files("mcp_server", includes=["**/*.md", "**/*.json"])
datas += collect_data_files("apps.admin_console", includes=["index.html"])
datas += [(str(frontend), "artemis/resources/showcase_ui")]
datas += [
    (str(root / "config/artemis.jsonc"), "artemis/resources/config"),
    (str(root / "mcp_server/rules.md"), "mcp_server"),
    (
        str(root / "packages/artemis-accessibility-helper/ArtemisAccessibilityHelper.apk"),
        "packages/artemis-accessibility-helper",
    ),
    (
        str(root / "packages/artemis-accessibility-helper/helper_manifest.json"),
        "packages/artemis-accessibility-helper",
    ),
]
for package in (
    "artemis", "artemis-client", "mcp", "langgraph", "langchain", "langchain-core",
    "langchain-community", "langchain-mcp-adapters", "google-genai", "langchain-google-genai",
    "langchain-google-vertexai", "langchain-openai", "langchain-anthropic",
    "pydantic", "fastapi", "uvicorn", "imageio-ffmpeg",
):
    try:
        datas += copy_metadata(package)
    except PackageNotFoundError:
        pass

hiddenimports = []
for package in (
    "artemis", "mcp_server", "apps.admin_console", "third_party.mobile_use",
    "ipykernel", "IPython",
):
    hiddenimports.extend(collect_submodules(package, on_error="warn"))

a = Analysis(
    [str(root / "artemis/__main__.py")],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "ruff", "pyright", "syrupy"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="artemis",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
)
