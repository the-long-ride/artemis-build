"""Artemis installation lifecycle: inventory, targeted cleanup, and preservation."""

import json
from pathlib import Path
import tomllib

import pytest

from artemis.interfaces.cli.commands import agent_lifecycle as lifecycle
from artemis.interfaces.cli.commands import agents


@pytest.fixture
def rules(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "rules.md"
    path.write_text("# Artemis testing\nInspect real devices before acting.\n", encoding="utf-8")
    monkeypatch.setattr(agents, "_rules_path", lambda: path)
    return path


def test_install_list_and_uninstall_only_one_target(tmp_path: Path, rules: Path) -> None:
    home = tmp_path / "home"
    agents.install_agent_skill("all", home=home)
    before = [r["target"] for r in lifecycle.installed_agents(home)]
    assert set(before) == set(agents.TARGETS)
    cli = home / ".claude/CLAUDE.md"
    cli.write_text("Personal instructions\n\n" + cli.read_text(), encoding="utf-8")

    deleted = lifecycle.uninstall_agent("claude", home=home)
    assert cli in deleted
    assert cli.read_text(encoding="utf-8").strip() == "Personal instructions"
    assert "claude" not in [r["target"] for r in lifecycle.installed_agents(home)]
    assert "codex" in [r["target"] for r in lifecycle.installed_agents(home)]
    assert (home / ".agents/skills/artemis-mobile-testing/SKILL.md").exists()
    assert lifecycle.uninstall_agent("claude", home=home) == []


def test_uninstall_all_cleans_skills_preserves_other_text(tmp_path: Path, rules: Path) -> None:
    home = tmp_path / "home"
    agents.install_agent_skill("all", home=home)
    codex = home / ".codex/AGENTS.md"
    codex.write_text("Codex personal notes\n\n" + codex.read_text(), encoding="utf-8")
    lifecycle.uninstall_agent("all", home=home)
    assert lifecycle.installed_agents(home) == []
    assert not (home / ".agents/skills/artemis-mobile-testing/SKILL.md").exists()
    assert codex.read_text(encoding="utf-8").strip() == "Codex personal notes"


def test_mcp_json_scoped_removal_and_legacy_rules(tmp_path: Path, rules: Path) -> None:
    home = tmp_path / "home"
    claude_json = home / ".claude.json"
    claude_json.parent.mkdir(parents=True)
    claude_json.write_text(
        json.dumps(
            {
                "theme": "dark",
                "mcpServers": {
                    "other": {"command": "other.exe"},
                    "artemis": {"command": "C:\\Tools\\artemis.exe", "args": ["mcp"]},
                },
            }
        ),
        encoding="utf-8",
    )
    rules_path = home / ".claude/rules/artemis.md"
    rules_path.parent.mkdir(parents=True)
    rules_path.write_text(rules.read_text(encoding="utf-8"), encoding="utf-8")
    found = lifecycle.installed_agents(home)
    assert [r["target"] for r in found] == ["claude"]
    assert found[0]["mcp"] == [claude_json]
    changed = lifecycle.uninstall_agent("claude", home=home)
    assert claude_json in changed and rules_path in changed
    result = json.loads(claude_json.read_text())
    assert result["theme"] == "dark"
    assert result["mcpServers"] == {"other": {"command": "other.exe"}}
    assert not rules_path.exists()


def test_codex_mcp_managed_block_and_unrelated_tables(tmp_path: Path, rules: Path) -> None:
    home = tmp_path / "home"
    config = home / ".codex/config.toml"
    config.parent.mkdir(parents=True)
    config.write_text(
        'model = "gpt-6"\n\n'
        '[mcp_servers.other]\ncommand = "other.exe"\n\n'
        "# BEGIN ARTEMIS MCP CONFIG\n"
        "[mcp_servers.artemis]\n"
        'command = "C:\\\\Tools\\\\artemis.exe"\nargs = ["mcp"]\n\n'
        '[mcp_servers.artemis.env]\nPYTHONUNBUFFERED = "1"\n'
        "# END ARTEMIS MCP CONFIG\n",
        encoding="utf-8",
    )
    assert lifecycle.installed_agents(home)[0]["target"] == "codex"
    lifecycle.uninstall_agent("codex", home=home)
    data = tomllib.loads(config.read_text())
    assert "artemis" not in data["mcp_servers"]
    assert data["mcp_servers"]["other"]["command"] == "other.exe"
    assert data["model"] == "gpt-6"


def test_uninstall_dry_run_keeps_everything(tmp_path: Path, rules: Path) -> None:
    home = tmp_path / "home"
    created = agents.install_agent_skill("claude", home=home)
    before = [path.read_bytes() for path in created]
    lifecycle.uninstall_agent("all", home=home, dry_run=True)
    assert [path.read_bytes() for path in created] == before


def test_skill_symlink_unlinks_not_destination(tmp_path: Path, rules: Path) -> None:
    home = tmp_path / "home"
    source = tmp_path / "artemis-mobile-testing" / "SKILL.md"
    source.parent.mkdir()
    source.write_text(
        "---\nname: artemis-mobile-testing\n---\n\n" + rules.read_text(),
        encoding="utf-8",
    )
    link = home / ".agents/skills/artemis-mobile-testing/SKILL.md"
    link.parent.mkdir(parents=True)
    link.symlink_to(source)
    lifecycle.uninstall_agent("all", home=home)
    assert not link.is_symlink()
    assert source.is_file()


def test_unmanaged_mcp_not_removed(tmp_path: Path, rules: Path) -> None:
    home = tmp_path / "home"
    config = home / ".claude.json"
    home.mkdir(parents=True)
    config.write_text(
        '{"mcpServers":{"artemis":{"command":"other.exe","args":[]}}}',
        encoding="utf-8",
    )
    assert lifecycle.uninstall_agent("claude", home=home) == []
    assert config.is_file()
    assert lifecycle.installed_agents(home) == []


def test_malformed_managed_block_refuses_uninstall(tmp_path: Path, rules: Path) -> None:
    home = tmp_path / "home"
    instruction = home / ".gemini/GEMINI.md"
    instruction.parent.mkdir(parents=True)
    instruction.write_text(agents.START, encoding="utf-8")
    with pytest.raises(ValueError, match="Unmatched"):
        lifecycle.uninstall_agent("antigravity", home=home)
    assert instruction.read_text() == agents.START
