"""Tests for configuration management."""

import pytest
from pathlib import Path

from wt.config import Config, ConfigError


def test_default_config(git_repo):
    """Test default configuration values."""
    config = Config(git_repo)
    assert config.get("prefix") == "feature"
    assert config.get("path_pattern") == "../{repo}-{name}"
    assert config.get("default_base") == "origin/main"


def test_save_and_load_config(git_repo, tmp_path, monkeypatch):
    """Test saving and loading config."""
    # Use temp directory for config
    monkeypatch.setenv("WT_CONFIG", str(tmp_path))

    config = Config(git_repo)
    config.set("prefix", "custom")
    config.save()

    # Load new config instance
    config2 = Config(git_repo)
    assert config2.get("prefix") == "custom"


def test_resolve_path_pattern(git_repo):
    """Test resolving path patterns."""
    config = Config(git_repo)

    # Test with default pattern
    path = config.resolve_path_pattern("feat", "feature/feat")
    assert path.name == "test-repo-feat"
    assert path.parent == git_repo.parent


def test_get_branch_name(git_repo):
    """Test getting full branch name."""
    config = Config(git_repo)
    branch = config.get_branch_name("feat")
    assert branch == "feature/feat"

    # Change prefix
    config.set("prefix", "wt")
    branch = config.get_branch_name("feat")
    assert branch == "wt/feat"


def test_extract_worktree_name(git_repo):
    """Test extracting worktree name from branch."""
    config = Config(git_repo)
    name = config.extract_worktree_name("feature/feat")
    assert name == "feat"

    # Without prefix
    name = config.extract_worktree_name("main")
    assert name == "main"


def test_set_invalid_key(git_repo):
    """Test setting invalid config key."""
    config = Config(git_repo)
    with pytest.raises(ConfigError):
        config.set("invalid_key", "value")


def test_config_without_repo():
    """Test config without a repository."""
    config = Config(None)
    assert config.get("prefix") == "feature"


def test_custom_path_pattern(git_repo):
    """Test custom path patterns."""
    config = Config(git_repo)
    config.set("path_pattern", "../worktrees/{name}")

    path = config.resolve_path_pattern("feat", "feature/feat")
    assert path.name == "feat"
    assert "worktrees" in str(path)


def test_get_config_path(tmp_path, monkeypatch):
    """Test getting config path."""
    # Use temp directory
    monkeypatch.setenv("WT_CONFIG", str(tmp_path))

    config = Config(None)
    path = config.get_config_path()
    assert path == tmp_path / ".wt.toml"


def test_get_config_path_default():
    """Test getting default config path."""
    config = Config(None)
    path = config.get_config_path()
    assert path == Path.home() / ".wt.toml"


def test_get_all(git_repo):
    """Test getting all config values."""
    config = Config(git_repo)
    all_config = config.get_all()
    assert "prefix" in all_config
    assert "path_pattern" in all_config
    assert "default_base" in all_config
