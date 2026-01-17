"""Pytest configuration and fixtures."""

import os
import shutil
import tempfile
from pathlib import Path

import pytest

from wt import git


@pytest.fixture
def temp_dir():
    """Create a temporary directory."""
    tmpdir = tempfile.mkdtemp()
    yield Path(tmpdir)
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def git_repo(temp_dir):
    """Create a temporary git repository."""
    repo_path = temp_dir / "test-repo"
    repo_path.mkdir()

    # Initialize git repo
    git.run_git(["init"], cwd=repo_path)
    git.run_git(["config", "user.name", "Test User"], cwd=repo_path)
    git.run_git(["config", "user.email", "test@example.com"], cwd=repo_path)
    # Disable GPG signing for tests
    git.run_git(["config", "commit.gpgsign", "false"], cwd=repo_path)
    git.run_git(["config", "tag.gpgsign", "false"], cwd=repo_path)

    # Create initial commit
    (repo_path / "README.md").write_text("# Test Repo\n")
    git.run_git(["add", "README.md"], cwd=repo_path)
    git.run_git(["commit", "-m", "Initial commit"], cwd=repo_path)

    # Create main branch (for newer git versions that use 'master')
    current_branch = git.get_current_branch(repo_path)
    if current_branch == "master":
        git.run_git(["branch", "-m", "main"], cwd=repo_path)

    yield repo_path


@pytest.fixture
def git_repo_with_remote(git_repo, temp_dir):
    """Create a git repository with a remote."""
    # Create bare remote
    remote_path = temp_dir / "test-remote.git"
    git.run_git(["init", "--bare"], cwd=remote_path)

    # Add remote to repo
    git.run_git(["remote", "add", "origin", str(remote_path)], cwd=git_repo)

    # Push main branch
    git.run_git(["push", "-u", "origin", "main"], cwd=git_repo)

    yield git_repo, remote_path


@pytest.fixture
def no_prompt(monkeypatch):
    """Disable user prompts for tests."""
    monkeypatch.setenv("WT_NO_PROMPT", "1")


@pytest.fixture
def change_dir(tmp_path):
    """Change to a temporary directory for the test."""
    original_dir = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(original_dir)
