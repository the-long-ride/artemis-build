"""Agent skill installation should preserve unrelated global instructions."""

from pathlib import Path

import pytest

from artemis.interfaces.cli.commands import agents


@pytest.fixture
def rules_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    rules = tmp_path / "rules.md"
    rules.write_text("# Artemis Testing\nVerify Android UI before code.\n", encoding="utf-8")
    monkeypatch.setattr(agents, "_rules_path", lambda: rules)
    return rules


def test_install_all_is_repeatable(tmp_path: Path, rules_file: Path) -> None:
    home = tmp_path / "home"
    claude = home / ".claude" / "CLAUDE.md"
    claude.parent.mkdir(parents=True)
    claude.write_text("# My own instructions\n", encoding="utf-8")

    expected = agents.install_agent_skill("all", home=home)
    first = [p.read_text(encoding="utf-8") for p in expected]
    assert len(expected) == 5
    assert "name: artemis-mobile-testing" in first[0]
    assert "# My own instructions" in claude.read_text(encoding="utf-8")
    assert all(s.count(agents.START) == 1 for s in first[1:])

    assert agents.install_agent_skill("all", home=home) == expected
    assert [p.read_text(encoding="utf-8") for p in expected] == first


def test_dry_run_does_not_write(tmp_path: Path, rules_file: Path) -> None:
    home = tmp_path / "home"
    result = agents.install_agent_skill("opencode", home=home, dry_run=True)
    assert len(result) == 2
    assert all(not file.exists() for file in result)


def test_modified_skill_requires_force(tmp_path: Path, rules_file: Path) -> None:
    home = tmp_path / "home"
    skill, _ = agents.install_agent_skill("codex", home=home)
    skill.write_text("custom content", encoding="utf-8")
    with pytest.raises(FileExistsError):
        agents.install_agent_skill("codex", home=home)
    agents.install_agent_skill("codex", home=home, force=True)
    assert "name: artemis-mobile-testing" in skill.read_text(encoding="utf-8")


def test_malformed_managed_block_does_not_overwrite(tmp_path: Path, rules_file: Path) -> None:
    home = tmp_path / "home"
    instructions = home / ".gemini" / "GEMINI.md"
    instructions.parent.mkdir(parents=True)
    instructions.write_text("# Existing\n" + agents.START, encoding="utf-8")
    with pytest.raises(ValueError, match="Unmatched"):
        agents.install_agent_skill("antigravity", home=home)
    assert not (home / ".agents").exists()
    assert instructions.read_text(encoding="utf-8").endswith(agents.START)
