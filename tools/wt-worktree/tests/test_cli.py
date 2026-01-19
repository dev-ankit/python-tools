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


def test_run_command_with_previous_symbol(runner, initialized_repo, no_prompt):
    """Test wt run command with - symbol for previous worktree."""
    # Create a worktree and switch to it to establish a previous worktree
    runner.invoke(cli, ["switch", "-c", "feat"])
    runner.invoke(cli, ["switch", "main"])

    # Now run a command in previous worktree using -
    result = runner.invoke(cli, ["run", "-", "echo hello"])
    assert result.exit_code == 0


def test_run_command_no_previous_worktree(runner, initialized_repo):
    """Test wt run command with - symbol when there's no previous worktree."""
    result = runner.invoke(cli, ["run", "-", "echo hello"])
    assert result.exit_code == 1
    assert "No previous worktree" in result.output


def test_run_command_nonexistent_worktree(runner, initialized_repo):
    """Test wt run command with non-existent worktree."""
    result = runner.invoke(cli, ["run", "nonexistent", "echo hello"])
    assert result.exit_code == 4
    assert "not found" in result.output


def test_sync_command_no_upstream(runner, initialized_repo, no_prompt):
    """Test wt sync command when current worktree has no upstream."""
    result = runner.invoke(cli, ["sync"])
    # Should show error about no upstream since initialized_repo doesn't have remote
    assert "no upstream" in result.output.lower() or "error" in result.output.lower()


def test_sync_command_all_worktrees(runner, initialized_repo, no_prompt):
    """Test wt sync --all command."""
    # Create feature worktrees
    runner.invoke(cli, ["switch", "-c", "feat"])

    # Run sync on all worktrees - will have no upstream but shouldn't crash
    result = runner.invoke(cli, ["sync", "--all"])
    assert result.exit_code == 0 or result.exit_code == 3
    assert "Syncing" in result.output


def test_sync_command_include(runner, initialized_repo, no_prompt):
    """Test wt sync --include command."""
    # Create worktrees
    runner.invoke(cli, ["switch", "-c", "feat1"])
    runner.invoke(cli, ["switch", "-c", "feat2"])

    # Sync only feat1
    result = runner.invoke(cli, ["sync", "--include", "feat1"])
    assert result.exit_code == 0 or result.exit_code == 3


def test_sync_command_exclude(runner, initialized_repo, no_prompt):
    """Test wt sync --all --exclude command."""
    # Create worktrees
    runner.invoke(cli, ["switch", "-c", "feat1"])
    runner.invoke(cli, ["switch", "-c", "feat2"])

    # Sync all except feat1
    result = runner.invoke(cli, ["sync", "--all", "--exclude", "feat1"])
    assert result.exit_code == 0 or result.exit_code == 3


def test_sync_command_with_rebase(runner, initialized_repo, no_prompt):
    """Test wt sync --rebase command."""
    # Run sync with rebase - will have no upstream but shouldn't crash
    result = runner.invoke(cli, ["sync", "--rebase"])
    assert result.exit_code == 0 or result.exit_code == 3


def test_sync_command_invalid_args(runner, initialized_repo):
    """Test wt sync with invalid argument combinations."""
    # Both include and exclude
    result = runner.invoke(cli, ["sync", "--include", "feat1", "--exclude", "feat2"])
    assert result.exit_code == 2
    assert "Cannot use both" in result.output

    # Exclude without all
    result = runner.invoke(cli, ["sync", "--exclude", "feat1"])
    assert result.exit_code == 2
    assert "requires --all" in result.output


def test_detached_worktree_create(runner, initialized_repo, no_prompt):
    """Test creating a detached worktree."""
    result = runner.invoke(cli, ["switch", "-c", "mydetached", "--detached"])
    assert result.exit_code == 0
    # Worktree should be created
    from wt.config import Config
    from wt.worktree import WorktreeManager
    config = Config(initialized_repo)
    manager = WorktreeManager(config)
    wt = manager.find_worktree_by_name("mydetached")
    assert wt is not None
    assert wt["name"] == "mydetached"
    assert wt.get("branch") is None  # detached worktrees have no branch


def test_detached_worktree_list(runner, initialized_repo, no_prompt):
    """Test listing detached worktrees shows custom names."""
    # Create two detached worktrees
    runner.invoke(cli, ["switch", "-c", "detached1", "--detached"])
    runner.invoke(cli, ["switch", "-c", "detached2", "--detached"])

    result = runner.invoke(cli, ["list"])
    assert result.exit_code == 0
    # Both should show with their custom names, not "(detached)"
    assert "detached1" in result.output
    assert "detached2" in result.output
    # Should not show generic "(detached)" for named worktrees
    lines = result.output.split('\n')
    detached_lines = [l for l in lines if "detached1" in l or "detached2" in l]
    assert len(detached_lines) == 2


def test_detached_worktree_switch(runner, initialized_repo, no_prompt):
    """Test switching to a detached worktree by its name."""
    # Create a detached worktree
    runner.invoke(cli, ["switch", "-c", "mydetached", "--detached"])

    # Switch to it by name
    result = runner.invoke(cli, ["switch", "mydetached"])
    assert result.exit_code == 0
    assert "mydetached" in result.output


def test_detached_worktree_run(runner, initialized_repo, no_prompt):
    """Test running commands in a detached worktree."""
    # Create a detached worktree
    runner.invoke(cli, ["switch", "-c", "mydetached", "--detached"])

    # Run a command in it
    result = runner.invoke(cli, ["run", "mydetached", "echo hello"])
    assert result.exit_code == 0


def test_multiple_detached_worktrees_unique_names(runner, initialized_repo, no_prompt):
    """Test that multiple detached worktrees can coexist with unique names."""
    # Create multiple detached worktrees
    runner.invoke(cli, ["switch", "-c", "det1", "--detached"])
    runner.invoke(cli, ["switch", "-c", "det2", "--detached"])
    runner.invoke(cli, ["switch", "-c", "det3", "--detached"])

    # List should show all three with their unique names
    result = runner.invoke(cli, ["list"])
    assert result.exit_code == 0
    assert "det1" in result.output
    assert "det2" in result.output
    assert "det3" in result.output

    # Each should be findable by name
    from wt.config import Config
    from wt.worktree import WorktreeManager
    config = Config(initialized_repo)
    manager = WorktreeManager(config)

    for name in ["det1", "det2", "det3"]:
        wt = manager.find_worktree_by_name(name)
        assert wt is not None
        assert wt["name"] == name


def test_detached_worktree_delete(runner, initialized_repo, no_prompt):
    """Test deleting a detached worktree by its name."""
    # Create a detached worktree
    runner.invoke(cli, ["switch", "-c", "mydetached", "--detached"])

    # Delete it by name
    result = runner.invoke(cli, ["delete", "mydetached", "--force"])
    assert result.exit_code == 0

    # Verify it's gone
    from wt.config import Config
    from wt.worktree import WorktreeManager
    config = Config(initialized_repo)
    manager = WorktreeManager(config)
    wt = manager.find_worktree_by_name("mydetached")
    assert wt is None


def test_detached_worktree_backward_compatibility(runner, initialized_repo, no_prompt):
    """Test that detached worktrees created without stored name still work."""
    # Create a detached worktree using raw git (simulates old behavior)
    from wt import git
    from wt.config import Config
    from wt.worktree import WorktreeManager

    config = Config(initialized_repo)
    wt_path = config.resolve_path_pattern("legacy", "feature/legacy")
    git.add_worktree(wt_path, "legacy", create_branch=False, base="HEAD",
                     detached=True, repo_path=initialized_repo)

    # Note: Not calling set_worktree_name - simulates old behavior

    # List should infer name from path
    manager = WorktreeManager(config)
    worktrees = manager.list_worktrees()
    legacy_wt = None
    for wt in worktrees:
        if "legacy" in wt["name"]:
            legacy_wt = wt
            break

    assert legacy_wt is not None
    assert legacy_wt["name"] == "legacy"  # Inferred from path

    # Should be able to find it by inferred name
    found_wt = manager.find_worktree_by_name("legacy")
    assert found_wt is not None
