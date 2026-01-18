"""Tests for git operations."""

import pytest
from pathlib import Path

from wt import git


def test_is_git_repo(git_repo, temp_dir):
    """Test git repo detection."""
    assert git.is_git_repo(git_repo) is True
    assert git.is_git_repo(temp_dir / "nonexistent") is False


def test_get_repo_root(git_repo):
    """Test getting repository root."""
    root = git.get_repo_root(git_repo)
    assert root == git_repo


def test_get_current_branch(git_repo):
    """Test getting current branch name."""
    branch = git.get_current_branch(git_repo)
    assert branch == "main"


def test_get_commit_hash(git_repo):
    """Test getting commit hash."""
    commit = git.get_commit_hash("HEAD", git_repo)
    assert len(commit) == 7  # Short hash


def test_get_commit_message(git_repo):
    """Test getting commit message."""
    message = git.get_commit_message("HEAD", git_repo)
    assert message == "Initial commit"


def test_has_uncommitted_changes(git_repo):
    """Test detecting uncommitted changes."""
    assert git.has_uncommitted_changes(git_repo) is False

    # Create uncommitted change
    (git_repo / "test.txt").write_text("test")
    assert git.has_uncommitted_changes(git_repo) is True


def test_branch_exists(git_repo):
    """Test checking if branch exists."""
    assert git.branch_exists("main", git_repo) is True
    assert git.branch_exists("nonexistent", git_repo) is False


def test_create_branch(git_repo):
    """Test creating a branch."""
    git.create_branch("test-branch", "HEAD", git_repo)
    assert git.branch_exists("test-branch", git_repo) is True


def test_list_worktrees(git_repo):
    """Test listing worktrees."""
    worktrees = git.list_worktrees(git_repo)
    assert len(worktrees) == 1
    assert worktrees[0]["path"] == git_repo
    assert worktrees[0]["branch"] == "main"


def test_add_worktree(git_repo, temp_dir):
    """Test adding a worktree."""
    wt_path = temp_dir / "test-worktree"
    git.add_worktree(wt_path, "test-branch", True, "HEAD", repo_path=git_repo)

    assert wt_path.exists()
    assert git.branch_exists("test-branch", git_repo)

    worktrees = git.list_worktrees(git_repo)
    assert len(worktrees) == 2

def test_add_worktree_with_existing_branch(git_repo, temp_dir):
    """Test adding a worktree with an existing branch."""
    git.create_branch("test-branch", "HEAD", git_repo)
    wt_path = temp_dir / "test-worktree"
    git.add_worktree(wt_path, "test-branch", False, "HEAD", repo_path=git_repo)

    assert wt_path.exists()
    assert git.branch_exists("test-branch", git_repo)

    worktrees = git.list_worktrees(git_repo)
    assert len(worktrees) == 2


def test_remove_worktree(git_repo, temp_dir):
    """Test removing a worktree."""
    wt_path = temp_dir / "test-worktree"
    git.add_worktree(wt_path, "test-branch", True, "HEAD", repo_path=git_repo)

    git.remove_worktree(wt_path, repo_path=git_repo)
    assert not wt_path.exists()


def test_delete_branch(git_repo):
    """Test deleting a branch."""
    git.create_branch("test-branch", "HEAD", git_repo)
    git.delete_branch("test-branch", force=True, path=git_repo)
    assert git.branch_exists("test-branch", git_repo) is False


def test_get_default_branch(git_repo):
    """Test getting default branch."""
    default = git.get_default_branch(git_repo)
    assert default == "main"


def test_worktree_exists(git_repo, temp_dir):
    """Test checking if worktree exists."""
    exists, path = git.worktree_exists("main", git_repo)
    assert exists is True
    assert path == git_repo

    exists, path = git.worktree_exists("nonexistent", git_repo)
    assert exists is False
    assert path is None


def test_get_status_short(git_repo):
    """Test getting short status."""
    status = git.get_status_short(git_repo)
    assert status == ""

    # Add uncommitted file
    (git_repo / "test.txt").write_text("test")
    status = git.get_status_short(git_repo)
    assert "test.txt" in status


def test_diff_trees(git_repo):
    """Test diffing between commits."""
    # Create a second commit
    (git_repo / "file2.txt").write_text("content")
    git.run_git(["add", "file2.txt"], cwd=git_repo)
    git.run_git(["commit", "-m", "Second commit"], cwd=git_repo)

    # Get diff
    diff = git.diff_trees("HEAD~1", "HEAD", git_repo)
    assert "file2.txt" in diff
