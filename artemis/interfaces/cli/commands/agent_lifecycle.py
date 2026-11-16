"""Inventory and safely uninstall Artemis global AI-agent integrations.

Remove only named Artemis MCP entries, marked instruction blocks and unmodified
Artemis skill/rule assets. Never follow a symlink while deleting its target.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
import tomllib
from typing import Annotated

import typer
from rich.console import Console

from artemis.interfaces.cli.commands import agents

console = Console()
ALL_TARGETS = (
    "claude",
    "opencode",
    "codex",
    "antigravity",
    "cursor",
    "windsurf",
    "vscode",
    "cline",
    "roo",
    "openclaw",
)
ALIASES = {"claude_code": "claude", "jetski": "antigravity", "roo_code": "roo"}
LEGACY_START = "<!-- BEGIN ARTEMIS MOBILE TESTING RULES -->"
LEGACY_END = "<!-- END ARTEMIS MOBILE TESTING RULES -->"
MCP_START = "# BEGIN ARTEMIS MCP CONFIG"
MCP_END = "# END ARTEMIS MCP CONFIG"


def _normalize(target: str) -> str:
    target = ALIASES.get(target.lower(), target.lower())
    if target != "all" and target not in ALL_TARGETS:
        raise ValueError(f"Unknown agent: {target}. Choose {', '.join(ALL_TARGETS)} or all.")
    return target


def _targets(target: str) -> tuple[str, ...]:
    return ALL_TARGETS if _normalize(target) == "all" else (_normalize(target),)


def _vscode_user_dir(home: Path) -> Path:
    if sys.platform == "win32":
        return home / "AppData" / "Roaming" / "Code" / "User"
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "Code" / "User"
    return home / ".config" / "Code" / "User"


def _codex_home(home: Path) -> Path:
    # Tests with a custom home must not inspect the actual user's CODEX_HOME.
    return (
        Path(os.environ["CODEX_HOME"]).expanduser()
        if home == Path.home() and os.getenv("CODEX_HOME")
        else home / ".codex"
    )


def _instruction_files(target: str, home: Path) -> list[Path]:
    if target == "claude":
        return [home / ".claude" / "CLAUDE.md"]
    if target == "opencode":
        return [home / ".config" / "opencode" / "AGENTS.md"]
    if target == "codex":
        return [_codex_home(home) / "AGENTS.md", _codex_home(home) / "AGENTS.override.md"]
    if target == "antigravity":
        return [home / ".gemini" / "GEMINI.md"]
    if target == "cursor":
        return [home / ".cursorrules"]
    if target == "windsurf":
        return [home / ".codeium" / "windsurf" / "memories" / "global_rules.md"]
    if target == "cline":
        return [home / ".clinerules"]
    if target == "roo":
        return [home / ".roorules"]
    if target == "openclaw":
        return [home / ".openclaw" / "OPENCLAW.md"]
    return []


def _legacy_rule_files(target: str, home: Path) -> list[Path]:
    if target == "claude":
        return [home / ".claude/rules/artemis.md"]
    if target == "antigravity":
        return [home / ".gemini/rules/artemis.md"]
    if target == "cursor":
        return [home / ".cursor/rules/artemis.mdc"]
    if target == "windsurf":
        return [home / ".codeium/windsurf/rules/artemis.md"]
    if target == "vscode":
        return [home / ".vscode/rules/artemis.md", _vscode_user_dir(home) / "rules/artemis.md"]
    if target == "cline":
        return [home / ".cline/rules/artemis.md"]
    if target == "roo":
        return [home / ".roo/rules/artemis.md"]
    if target == "openclaw":
        return [home / ".openclaw/rules/artemis.md"]
    return []


def _claude_desktop_file(home: Path) -> Path:
    if sys.platform == "win32":
        return home / "AppData/Roaming/Claude/claude_desktop_config.json"
    if sys.platform == "darwin":
        return home / "Library/Application Support/Claude/claude_desktop_config.json"
    return home / ".config/Claude/claude_desktop_config.json"


def _mcp_files(target: str, home: Path) -> list[tuple[Path, tuple[str, ...]]]:
    std = ("mcpServers",)
    if target == "claude":
        return [(home / ".claude.json", std), (_claude_desktop_file(home), std)]
    if target == "codex":
        return [(_codex_home(home) / "config.toml", ("mcp_servers",))]
    if target == "antigravity":
        return [
            (home / ".gemini/jetski/mcp_config.json", std),
            (home / ".gemini/antigravity/mcp_config.json", std),
            (home / ".gemini/config/mcp_config.json", std),
        ]
    if target == "cursor":
        return [(home / ".cursor/mcp.json", std)]
    if target == "windsurf":
        return [(home / ".codeium/windsurf/mcp_config.json", std)]
    if target == "vscode":
        return [
            (_vscode_user_dir(home) / "mcp.json", ("servers",)),
            (home / ".copilot/mcp-config.json", ("servers",)),
        ]
    if target == "cline":
        return [
            (home / ".cline/data/settings/cline_mcp_settings.json", std),
            (home / ".cline/mcp.json", std),
            (
                _vscode_user_dir(home)
                / "globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json",
                std,
            ),
        ]
    if target == "roo":
        from mcp_server.utils.env_utils import get_project_root

        roo_paths = [
            (
                _vscode_user_dir(home)
                / "globalStorage/rooveterinaryinc.roo-cline/settings/mcp_settings.json",
                std,
            ),
            (
                _vscode_user_dir(home)
                / "globalStorage/rooveterinaryinc.roo-cline/settings/cline_mcp_settings.json",
                std,
            ),
        ]
        if home == Path.home():
            roo_paths.append((Path(get_project_root()) / ".roo/mcp.json", std))
        return roo_paths
    if target == "openclaw":
        return [(home / ".openclaw/openclaw.json", ("mcp", "servers"))]
    if target == "opencode":
        return [(home / ".config/opencode/opencode.json", ("mcp",))]
    return []


def _exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _rules_content() -> str:
    return agents._rules_path().read_text(encoding="utf-8").strip()


def _skill_path(home: Path) -> Path:
    return home / ".agents/skills" / agents.SKILL_NAME / "SKILL.md"


def _owned_file(path: Path, rule_text: str, cursor: bool = False) -> bool:
    if not _exists(path):
        return False
    if path.is_symlink():
        # Only a named Artemis rule link to a named Artemis rule/skill may be
        # unlinked. NEVER delete its destination.
        resolved = path.resolve(strict=False)
        return resolved.name in ("artemis.md", "artemis.mdc", "SKILL.md") and (
            resolved.parent.name in ("rules", agents.SKILL_NAME) or resolved.stem == "artemis"
        )
    actual = path.read_text(encoding="utf-8").strip()
    if cursor:
        return actual.endswith(rule_text) and actual.startswith("---\n")
    return actual == rule_text


def _owned_skill(path: Path, rule_text: str) -> bool:
    if not _exists(path):
        return False
    if path.is_symlink():
        resolved = path.resolve(strict=False)
        return resolved.name == "SKILL.md" and resolved.parent.name == agents.SKILL_NAME
    text = path.read_text(encoding="utf-8")
    return f"name: {agents.SKILL_NAME}" in text and text.rstrip().endswith(rule_text)


def _owned_mcp(entry: object) -> bool:
    if not isinstance(entry, dict):
        return False
    cmd = entry.get("command")
    args = entry.get("args", [])
    if isinstance(cmd, list):
        cmd, args = (cmd[0], cmd[1:]) if cmd else (None, [])
    if not isinstance(cmd, str):
        return False
    exe = cmd.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return (exe in ("artemis.exe", "artemis") and args in (["mcp"], [])) or (
        exe in ("python", "python.exe", "python3", "python3.exe") and args == ["-m", "mcp_server"]
    )


def _read_mcp(path: Path, keys: tuple[str, ...]) -> bool:
    if not path.is_file():
        return False
    if path.is_symlink():
        return False
    if path.suffix == ".toml":
        obj = tomllib.loads(path.read_text(encoding="utf-8"))
    else:
        obj = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(obj, dict):
        raise ValueError(f"Invalid MCP configuration object: {path}")
    for key in keys:
        obj = obj.get(key, {})
        if not isinstance(obj, dict):
            raise ValueError(f"Invalid MCP configuration section: {path}")
    return _owned_mcp(obj.get("artemis"))


def _block_present(path: Path) -> bool:
    if not path.is_file() or path.is_symlink():
        return False
    data = path.read_text(encoding="utf-8")
    return (agents.START in data and agents.END in data) or (
        LEGACY_START in data and LEGACY_END in data
    )


def installed_agents(home: Path | None = None) -> list[dict]:
    """Read real global integrations; no user-wide binary/IDE scan is required."""
    home = home or Path.home()
    rule_text = _rules_content()
    result = []
    for target in ALL_TARGETS:
        mcp_files = [p for p, keys in _mcp_files(target, home) if _read_mcp(p, keys)]
        instructions = [p for p in _instruction_files(target, home) if _block_present(p)]
        skills = [
            p
            for p in _legacy_rule_files(target, home)
            if _owned_file(p, rule_text, cursor=p.suffix == ".mdc")
        ]
        if mcp_files or instructions or skills:
            result.append(
                {
                    "target": target,
                    "mcp": mcp_files,
                    "instructions": instructions,
                    "rules": skills,
                }
            )
    return result


def _remove_blocks(path: Path, *, dry_run: bool) -> bool:
    if not _exists(path):
        return False
    if path.is_symlink():
        raise ValueError(f"Refusing to rewrite linked global instruction file: {path}")
    original = path.read_text(encoding="utf-8")
    current = original
    for start, end in ((agents.START, agents.END), (LEGACY_START, LEGACY_END)):
        if (start in current) != (end in current):
            raise ValueError(f"Unmatched Artemis instruction markers: {path}")
        if start not in current:
            continue
        pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
        current = pattern.sub("", current)
    if current == original:
        return False
    current = current.strip() + "\n" if current.strip() else ""
    print(f"  {'Would remove' if dry_run else 'Removed'} Artemis instructions: {path}")
    if not dry_run:
        if current:
            path.write_text(current, encoding="utf-8")
        else:
            path.unlink()
    return True


def _remove_json_mcp(path: Path, keys: tuple[str, ...], *, dry_run: bool) -> bool:
    if not _read_mcp(path, keys):
        return False
    root = json.loads(path.read_text(encoding="utf-8-sig"))
    section = root
    for key in keys:
        section = section[key]
    del section["artemis"]
    # Do not delete unrelated metadata or empty parents: preserves user config.
    print(f"  {'Would remove' if dry_run else 'Removed'} Artemis MCP: {path}")
    if not dry_run:
        path.write_text(json.dumps(root, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def _remove_codex(path: Path, *, dry_run: bool) -> bool:
    if not _read_mcp(path, ("mcp_servers",)):
        return False
    original = path.read_text(encoding="utf-8")
    if (MCP_START in original) != (MCP_END in original):
        raise ValueError(f"Unmatched Artemis MCP markers: {path}")
    if MCP_START in original:
        pattern = re.compile(
            r"(?ms)^" + re.escape(MCP_START) + r"\n.*?^" + re.escape(MCP_END) + r"\n?"
        )
        result, count = pattern.subn("", original, count=1)
        if not count:
            raise ValueError(f"Nonstandard Artemis MCP block: {path}")
    else:
        # Older code wrote bare tables; remove them plus nested env tables.
        pattern = re.compile(r"(?m)^\s*\[mcp_servers\.artemis(?:\.[^\]]+)?\]\s*$")
        lines = original.splitlines(keepends=True)
        kept: list[str] = []
        skipping = False
        matched = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("["):
                if pattern.fullmatch(stripped):
                    skipping, matched = True, True
                    continue
                skipping = False
            if not skipping:
                kept.append(line)
        if not matched:
            raise ValueError(f"Cannot safely parse legacy Codex MCP entry: {path}")
        result = "".join(kept)
    obj = tomllib.loads(result)
    if "artemis" in obj.get("mcp_servers", {}):
        raise ValueError(f"Artemis MCP TOML cleanup incomplete: {path}")
    print(f"  {'Would remove' if dry_run else 'Removed'} Artemis MCP: {path}")
    if not dry_run:
        path.write_text(result, encoding="utf-8")
    return True


def uninstall_agent(
    target: str = "all", *, home: Path | None = None, dry_run: bool = False
) -> list[Path]:
    """Remove all Artemis-managed integrations for target(s), keeping user data."""
    home = home or Path.home()
    rule_text = _rules_content()
    changed: list[Path] = []
    for item in _targets(target):
        for path, keys in _mcp_files(item, home):
            if (
                _remove_codex(path, dry_run=dry_run)
                if path.suffix == ".toml"
                else (_remove_json_mcp(path, keys, dry_run=dry_run))
            ):
                changed.append(path)
        for path in _instruction_files(item, home):
            if _remove_blocks(path, dry_run=dry_run):
                changed.append(path)
        for path in _legacy_rule_files(item, home):
            if not _owned_file(path, rule_text, cursor=path.suffix == ".mdc"):
                continue
            print(f"  {'Would unlink' if dry_run else 'Unlinked'} Artemis rule: {path}")
            if not dry_run:
                path.unlink()
            changed.append(path)
    skill = _skill_path(home)
    # Shared skill survives a per-agent uninstall if any other installed
    # agent still uses its managed pointer. On --all no pointers remain.
    managed_pointers = [
        p for name in agents.TARGETS for p in _instruction_files(name, home) if _block_present(p)
    ]
    if (target == "all" or not managed_pointers) and _owned_skill(skill, rule_text):
        print(f"  {'Would remove' if dry_run else 'Removed'} Artemis skill: {skill}")
        if not dry_run:
            skill.unlink()
            try:
                skill.parent.rmdir()
            except OSError:
                pass
        changed.append(skill)
    return changed


def _print_list() -> None:
    records = installed_agents()
    if not records:
        console.print("No Artemis AI-agent integrations found.")
        return
    for item in records:
        console.print(
            f"{item['target']}: MCP={len(item['mcp'])}, "
            f"instructions={len(item['instructions'])}, rules={len(item['rules'])}"
        )


def _uninstall_cli(
    target: Annotated[str | None, typer.Argument(help="Agent name (or use --target)")] = None,
    target_option: Annotated[str | None, typer.Option("--target", "-t")] = None,
    all_targets: Annotated[
        bool, typer.Option("--all", help="Uninstall all supported agents")
    ] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview changes")] = False,
) -> None:
    try:
        if sum((bool(target), bool(target_option), all_targets)) != 1:
            raise ValueError("Specify one agent, --target AGENT or --all")
        chosen = "all" if all_targets else (target_option or target)
        changed = uninstall_agent(chosen, dry_run=dry_run)
        if not changed:
            console.print("No matching Artemis-owned integrations found.")
    except (OSError, ValueError) as exc:
        console.print(f"[red]Uninstall failed: {exc}[/red]")
        raise typer.Exit(1) from exc


def register_commands(app: typer.Typer) -> None:
    app.command("uninstall", help="Remove Artemis MCP, rules and skills for an AI agent.")(
        _uninstall_cli
    )
    app.command("installed-list", help="List AI agents configured to use Artemis.")(_print_list)
