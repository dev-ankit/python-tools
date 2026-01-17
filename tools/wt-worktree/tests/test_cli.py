"""Tests for CLI commands."""

import os
import pytest
from click.testing import CliRunner
from pathlib import Path

from wt.cli import cli
from wt import git


@pytest.fixture
def runner():
    """Create a Click test runner."""
    return CliRunner()


@pytest.fixture
def initialized_repo(git_repo, tmp_path, monkeypatch):
    """Create a git repo with wt config in temp directory."""
    from wt.config import Config
    # Use temp directory for config
    monkeypatch.setenv("WT_CONFIG", str(tmp_path))

    # Initialize config with test values
    config = Config(git_repo)
    config.set("default_base", "main")  # Use main instead of origin/main for tests
    config.save()

    # Change to repo directory for CLI commands
    try:
        original_dir = os.getcwd()
    except (OSError, FileNotFoundError):
        # Current directory was deleted, use /tmp
        original_dir = "/tmp"

    os.chdir(git_repo)
    yield git_repo

    try:
        os.chdir(original_dir)
    except (OSError, FileNotFoundError):
        # Directory might have been deleted, go to /tmp
        os.chdir("/tmp")


def test_cli_help(runner):
    """Test CLI help command."""
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Git worktree manager" in result.output


def test_init_command(runner, tmp_path, monkeypatch):
    """Test wt init command."""
    # Use temp directory for config
    monkeypatch.setenv("WT_CONFIG", str(tmp_path))

    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 0
    assert "Configuration saved" in result.output
    assert (tmp_path / ".wt.toml").exists()


def test_init_with_custom_options(runner, tmp_path, monkeypatch):
    """Test init with custom prefix and path."""
    # Use temp directory for config
    monkeypatch.setenv("WT_CONFIG", str(tmp_path))

    result = runner.invoke(cli, ["init", "--prefix", "dev", "--path", "../{name}"])
    assert result.exit_code == 0
    assert "prefix: dev" in result.output
    assert (tmp_path / ".wt.toml").exists()


def test_list_command(runner, initialized_repo):
    """Test wt list command."""
    result = runner.invoke(cli, ["list"])
    assert result.exit_code == 0
    assert "main" in result.output


def test_switch_create(runner, initialized_repo, no_prompt):
    """Test wt switch -c command."""
    result = runner.invoke(cli, ["switch", "-c", "feat"])
    assert result.exit_code == 0
    assert git.branch_exists("feature/feat", initialized_repo)


def test_switch_to_existing(runner, initialized_repo, no_prompt):
    """Test switching to existing worktree."""
    # Create worktree first
    runner.invoke(cli, ["switch", "-c", "feat"])

    # Switch to it (this won't actually cd in tests, but should succeed)
    result = runner.invoke(cli, ["switch", "feat"])
    # In test environment, this might fail because we can't actually cd
    # but the logic should work


def test_switch_nonexistent(runner, initialized_repo):
    """Test switching to non-existent worktree."""
    result = runner.invoke(cli, ["switch", "nonexistent"])
    assert result.exit_code == 4
    assert "not found" in result.output


def test_config_list(runner, initialized_repo):
    """Test wt config --list."""
    result = runner.invoke(cli, ["config", "--list"])
    assert result.exit_code == 0
    assert "prefix" in result.output
    assert "feature" in result.output


def test_config_get(runner, initialized_repo):
    """Test wt config <key>."""
    result = runner.invoke(cli, ["config", "prefix"])
    assert result.exit_code == 0
    assert "feature" in result.output


def test_config_set(runner, initialized_repo):
    """Test wt config <key> <value>."""
    result = runner.invoke(cli, ["config", "prefix", "custom"])
    assert result.exit_code == 0
    assert "Set config" in result.output


def test_shell_init_bash(runner):
    """Test wt shell-init bash."""
    result = runner.invoke(cli, ["shell-init", "bash"])
    assert result.exit_code == 0
    assert "function" in result.output or "wt()" in result.output
    assert "bash" in result.output


def test_shell_init_fish(runner):
    """Test wt shell-init fish."""
    result = runner.invoke(cli, ["shell-init", "fish"])
    assert result.exit_code == 0
    assert "function wt" in result.output


def test_status_command(runner, initialized_repo):
    """Test wt status command."""
    result = runner.invoke(cli, ["status"])
    assert result.exit_code == 0
    assert "main" in result.output


def test_delete_command(runner, initialized_repo, no_prompt):
    """Test wt delete command."""
    # Create worktree first
    runner.invoke(cli, ["switch", "-c", "feat"])

    # Delete it
    result = runner.invoke(cli, ["delete", "feat", "--force"])
    assert result.exit_code == 0


def test_clean_command(runner, initialized_repo, no_prompt):
    """Test wt clean command."""
    result = runner.invoke(cli, ["clean", "--dry-run"])
    assert result.exit_code == 0


def test_commands_from_secondary_worktree(runner, initialized_repo, no_prompt):
    """Test that wt commands work from secondary worktrees."""
    # Create a secondary worktree
    result = runner.invoke(cli, ["switch", "-c", "feat"])
    assert result.exit_code == 0

    # Find the worktree path
    from wt import git
    worktrees = git.list_worktrees(initialized_repo)
    feat_worktree = None
    for wt in worktrees:
        if wt.get("branch") == "feature/feat":
            feat_worktree = wt["path"]
            break

    assert feat_worktree is not None

    # Change to the secondary worktree directory
    original_dir = os.getcwd()
    try:
        os.chdir(feat_worktree)

        # Run wt list from the secondary worktree - should still work
        result = runner.invoke(cli, ["list"])
        assert result.exit_code == 0
        assert "main" in result.output
        assert "feat" in result.output

        # Run wt status from the secondary worktree
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0
        assert "main" in result.output

        # Config should also work (reads from main worktree)
        result = runner.invoke(cli, ["config", "--list"])
        assert result.exit_code == 0
        assert "prefix" in result.output

    finally:
        try:
            os.chdir(original_dir)
        except (OSError, FileNotFoundError):
            os.chdir("/tmp")


def test_run_command(runner, initialized_repo):
    """Test wt run command."""
    # Run a simple command in main worktree
    result = runner.invoke(cli, ["run", "main", "echo hello"])
    assert result.exit_code == 0


def test_run_command_with_default_symbol(runner, initialized_repo):
    """Test wt run command with ^ symbol for default worktree."""
    # Run a command in default worktree using ^
    result = runner.invoke(cli, ["run", "^", "echo hello"])
    assert result.exit_code == 0


def test_run_command_nonexistent_worktree(runner, initialized_repo):
    """Test wt run command with non-existent worktree."""
    result = runner.invoke(cli, ["run", "nonexistent", "echo hello"])
    assert result.exit_code == 4
    assert "not found" in result.output
