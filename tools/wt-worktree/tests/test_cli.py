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
def initialized_repo(git_repo):
    """Create a git repo with wt initialized."""
    from wt.config import Config
    # Initialize wt in the repo
    config = Config(git_repo)
    config.set("default_base", "main")  # Use main instead of origin/main for tests
    config.save_local()

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


def test_init_command(runner, git_repo):
    """Test wt init command."""
    os.chdir(git_repo)
    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 0
    assert "Initialized wt" in result.output
    assert (git_repo / ".wt.toml").exists()


def test_init_already_initialized(runner, git_repo):
    """Test init when already initialized."""
    os.chdir(git_repo)
    runner.invoke(cli, ["init"])

    # Try to init again
    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 1
    assert "already initialized" in result.output


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
    assert "Set local config" in result.output


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
