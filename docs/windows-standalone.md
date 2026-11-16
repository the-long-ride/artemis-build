# Windows standalone executable (GitHub Actions)

The `windows-exe.yml` workflow produces an **x64 Windows terminal executable**
named `artemis.exe`, using `uv sync --locked` to install the source project's
Python runtime and PyInstaller to freeze the console entry point. The UI's
production Angular build, Artemis config, MCP rules, agent prompts, and Android
Accessibility Helper APK are bundled. The final `.exe` runs **without Python,
uv, Node, or a repository checkout** on the target machine.

## Build and download

1. Open **Actions > Windows standalone Artemis executable > Run workflow** on
   the feature branch, or open a PR to trigger the workflow.
2. Download the `artemis-windows-x64-exe` artifact, unzip it, and keep
   `artemis.exe` in a permanent folder on your PATH. Validate its SHA256 against
   `artemis.exe.sha256`.
3. Run these commands in PowerShell:

```powershell
.\artemis.exe --help
.\artemis.exe init
.\artemis.exe doctor
.\artemis.exe run "Open Android Settings" --profile flash
.\artemis.exe ui --no-open
```

This is a one-file Python executable, not a native-code rewrite. On first
launch PyInstaller unpacks its data into a temporary directory. Config,
credentials, traces and logs are stored in Artemis' user application directory,
not inside the unpacked bundle.

**External system requirements remain:** a Windows machine, an authorized
Android device/emulator, the Android Debug Bridge (ADB) toolchain, and valid LLM
provider credentials. Optional media tooling (e.g. FFmpeg or scrcpy) is not
provided by the exe. Some operations still require network/API access. Device
testing needs real hardware or an emulator; CI smoke tests only validate CLI
startup, MCP configuration, and the agent installer.

## AI agent setup

The repo contains `mcp_server/rules.md` rather than a pre-existing
`SKILL.md`. Artemis converts these rules into a managed, installable skill at
`~/.agents/skills/artemis-mobile-testing/SKILL.md`, adding a short pointer to
your chosen global agent instructions while preserving other content:

```powershell
.\artemis.exe agents install --target all --dry-run
.\artemis.exe agents install --target all
.\artemis.exe agents install --target claude
.\artemis.exe agents install --target codex
.\artemis.exe agents install --target opencode
.\artemis.exe agents install --target antigravity
```

Claude Code uses `~/.claude/CLAUDE.md`; Codex uses
`$CODEX_HOME/AGENTS.md` (or `~/.codex/AGENTS.md`); OpenCode uses
`~/.config/opencode/AGENTS.md`; Antigravity uses
`~/.gemini/GEMINI.md`. Installation is idempotent. Changed skill content is
not replaced without `--force`. This command **does not** register an MCP
server; to install MCP configuration as well, run:

```powershell
.\artemis.exe mcp --install all
```

For frozen binaries, generated MCP configuration uses `artemis.exe mcp` as
the server process instead of `python -m mcp_server`.

## Uninstall an AI integration or list installed agents

Use the executable to inspect global integrations and remove just
Artemis-owned registration, rules, and skill references. Use a named
target to keep other agents registered, or `--all` to clear all supported
Artemis integrations, without deleting the binary, traces, ADB or your own
agent instructions.

```powershell
.\artemis.exe installed-list
.\artemis.exe uninstall --target claude
.\artemis.exe uninstall --target codex
.\artemis.exe uninstall --target opencode
.\artemis.exe uninstall --target antigravity
.\artemis.exe uninstall --all --dry-run
.\artemis.exe uninstall --all
```

The command also recognizes `cursor`, `windsurf`, `vscode`, `cline`,
`roo`, and `openclaw` integrations installed by `artemis mcp --install all`.
Only the `artemis` MCP key, managed instruction blocks, and unmodified
Artemis-owned rule/skill files are removed. The common
`~/.agents/skills/artemis-mobile-testing/SKILL.md` is retained during
per-target uninstall while another installed agent references it. Links to
owned skill files are unlinked without following or deleting their targets.
Unrecognized/modified files and other MCP entries are preserved.
