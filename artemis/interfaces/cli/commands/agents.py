"""Install Artemis' mobile-testing guidance as a portable agent skill.

No dependency on the source checkout: the source rules are collected into the
frozen executable and also shipped with the Python distribution.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Annotated

import typer
from rich.console import Console

agents_app = typer.Typer(help="Install Artemis skills and global AI coding-agent instructions.")
console = Console()

SKILL_NAME = "artemis-mobile-testing"
START = "<!-- BEGIN ARTEMIS SKILL -->"
END = "<!-- END ARTEMIS SKILL -->"
TARGETS = ("claude", "opencode", "codex", "antigravity")


def _rules_path() -> Path:
    """Locate immutable rules in a checkout, wheel, or PyInstaller bundle."""
    roots = [
        Path(getattr(sys, "_MEIPASS", "")) if getattr(sys, "frozen", False) else None,
        Path(__file__).resolve().parents[4],
    ]
    for root in roots:
        if root is not None:
            candidate = root / "mcp_server" / "rules.md"
            if candidate.is_file():
                return candidate
    raise FileNotFoundError(
        "Artemis rules.md was not packaged. Rebuild with mcp_server/rules.md included."
    )


def _target_file(target: str, home: Path) -> Path:
    if target == "claude":
        return home / ".claude" / "CLAUDE.md"
    if target == "opencode":
        return home / ".config" / "opencode" / "AGENTS.md"
    if target == "codex":
        codex_home = Path(os.environ.get("CODEX_HOME", str(home / ".codex"))).expanduser()
        override = codex_home / "AGENTS.override.md"
        return override if override.is_file() and override.read_text(encoding="utf-8").strip() else codex_home / "AGENTS.md"
    if target == "antigravity":
        return home / ".gemini" / "GEMINI.md"
    raise ValueError(f"Unsupported AI coding agent: {target}")


def _upsert_block(file_path: Path, text: str, *, dry_run: bool = False) -> None:
    """Replace only the managed block; reject malformed markers and unreadable files."""
    old = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
    if (START in old) != (END in old):
        raise ValueError(f"Unmatched Artemis instruction markers in {file_path}")
    if START in old:
        before, rest = old.split(START, 1)
        _, after = rest.split(END, 1)
        result = (before.rstrip() + "\n\n" if before.strip() else "") + text + after
    else:
        result = (old.rstrip() + "\n\n" if old.strip() else "") + text + "\n"
    if result == old or dry_run:
        return
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(result, encoding="utf-8")


def install_agent_skill(
    target: str = "all",
    *,
    home: Path | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> list[Path]:
    """Install shared skill and small pointers in the selected global instruction files.

    Existing personal instructions are preserved. A modified skill is not overwritten
    unless force=True. No project-local AI instructions are touched.
    """
    if target != "all" and target not in TARGETS:
        raise ValueError(f"Unsupported target {target!r}. Choose {', '.join(TARGETS)} or all.")
    home = home or Path.home()
    rules = _rules_path().read_text(encoding="utf-8").strip()
    skill_file = home / ".agents" / "skills" / SKILL_NAME / "SKILL.md"
    frontmatter = (
        "---\n"
        "name: artemis-mobile-testing\n"
        "description: Explore and test Android applications using Artemis CLI or MCP with evidence-grounded device interaction.\n"
        "---\n\n"
    )
    skill_text = frontmatter + rules + "\n"
    if skill_file.is_file() and skill_file.read_text(encoding="utf-8") != skill_text and not force:
        raise FileExistsError(
            f"{skill_file} has local changes; use --force to replace the Artemis-managed skill."
        )
    targets = TARGETS if target == "all" else (target,)
    destinations = [skill_file] + [_target_file(name, home) for name in targets]
    pointer = (
        f"{START}\n"
        "For Android/mobile UI exploration and testing, use the Artemis mobile-testing "
        f"skill at `{skill_file}`. Read its SKILL.md before planning mobile UI "
        "automation or writing device tests. Use Artemis CLI/MCP for verified device "
        "state; do not invent UI elements or results.\n"
        f"{END}"
    )
    # Validate all existing instruction files before writing any.
    for dest in destinations[1:]:
        old = dest.read_text(encoding="utf-8") if dest.is_file() else ""
        if (START in old) != (END in old):
            raise ValueError(f"Unmatched Artemis instruction markers in {dest}")
    if not dry_run and (not skill_file.exists() or force or skill_file.read_text(encoding="utf-8") != skill_text):
        skill_file.parent.mkdir(parents=True, exist_ok=True)
        skill_file.write_text(skill_text, encoding="utf-8")
    for dest in destinations[1:]:
        _upsert_block(dest, pointer, dry_run=dry_run)
    return destinations


@agents_app.command("install")
def install_command(
    target: Annotated[str, typer.Option("--target", "-t", help="claude, opencode, codex, antigravity, or all")] = "all",
    dry_run: Annotated[bool, typer.Option("--dry-run", help="List changes without writing files")] = False,
    force: Annotated[bool, typer.Option("--force", help="Replace an edited Artemis-managed SKILL.md")] = False,
) -> None:
    """Install ~/.agents/skills/artemis-mobile-testing and global agent guidance."""
    try:
        destinations = install_agent_skill(target.lower(), dry_run=dry_run, force=force)
    except (OSError, ValueError) as exc:
        console.print(f"[red]Unable to install agent skill: {exc}[/red]")
        raise typer.Exit(code=1) from exc
    verb = "Would install/update" if dry_run else "Installed/updated"
    for path in destinations:
        console.print(f"[green]{verb}[/green]: {path}")
