"""Git operations wrapper module."""

import subprocess
import sys
from pathlib import Path
from typing import Optional, List, Tuple


class GitError(Exception):
    """Raised when a git operation fails."""
    pass


def run_git(args: List[str], cwd: Optional[Path] = None, check: bool = True,
            capture_output: bool = True) -> subprocess.CompletedProcess:
    """
    Run a git command and return the result.

    Args:
        args: Git command arguments (without 'git' prefix)
        cwd: Working directory for the command
        check: Raise GitError if command fails
        capture_output: Capture stdout/stderr

    Returns:
        CompletedProcess object

    Raises:
        GitError: If command fails and check=True
    """
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=capture_output,
            text=True,
            check=False
        )

        if check and result.returncode != 0:
            raise GitError(f"Git command failed: {' '.join(args)}\n{result.stderr}")

        return result
    except FileNotFoundError:
        raise GitError("Git is not installed or not in PATH")


def is_git_repo(path: Optional[Path] = None) -> bool:
    """Check if the given path is inside a git repository."""
    try:
        run_git(["rev-parse", "--git-dir"], cwd=path)
        return True
    except GitError:
        return False


def get_repo_root(path: Optional[Path] = None) -> Path:
    """
    Get the root directory of the git repository (current worktree).

    Raises:
        GitError: If not in a git repository
    """
    result = run_git(["rev-parse", "--show-toplevel"], cwd=path)
    return Path(result.stdout.strip())


def get_main_worktree_root(path: Optional[Path] = None) -> Path:
    """
    Get the root directory of the main worktree (where .git is a directory).

    This is important because .wt.toml is stored in the main worktree,
    but we might be running commands from a secondary worktree.

    Raises:
        GitError: If not in a git repository
    """
    # List all worktrees - the first one is always the main worktree
    worktrees = list_worktrees(path)
    if not worktrees:
        raise GitError("No worktrees found")

    # Return the path of the first worktree (main worktree)
    return worktrees[0]["path"]


def get_current_branch(path: Optional[Path] = None) -> str:
    """
    Get the name of the current branch.

    Returns empty string if in detached HEAD state.
    """
    result = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=path)
    branch = result.stdout.strip()
    return "" if branch == "HEAD" else branch


def get_commit_hash(ref: str = "HEAD", path: Optional[Path] = None) -> str:
    """Get the commit hash for a given ref."""
    result = run_git(["rev-parse", "--short", ref], cwd=path)
    return result.stdout.strip()


def get_commit_message(ref: str = "HEAD", path: Optional[Path] = None) -> str:
    """Get the commit message for a given ref."""
    result = run_git(["log", "-1", "--pretty=%s", ref], cwd=path)
    return result.stdout.strip()


def has_uncommitted_changes(path: Optional[Path] = None) -> bool:
    """Check if there are uncommitted changes (staged or unstaged)."""
    result = run_git(["status", "--porcelain"], cwd=path)
    return bool(result.stdout.strip())


def get_status_short(path: Optional[Path] = None) -> str:
    """Get short status output."""
    result = run_git(["status", "--porcelain"], cwd=path)
    return result.stdout


def branch_exists(branch: str, path: Optional[Path] = None) -> bool:
    """Check if a branch exists locally."""
    result = run_git(["rev-parse", "--verify", f"refs/heads/{branch}"],
                     cwd=path, check=False)
    return result.returncode == 0


def remote_branch_exists(branch: str, remote: str = "origin",
                        path: Optional[Path] = None) -> bool:
    """Check if a branch exists on remote."""
    result = run_git(["rev-parse", "--verify", f"refs/remotes/{remote}/{branch}"],
                     cwd=path, check=False)
    return result.returncode == 0


def create_branch(branch: str, base: str = "HEAD", path: Optional[Path] = None):
    """
    Create a new branch from base.

    Raises:
        GitError: If branch creation fails
    """
    run_git(["branch", branch, base], cwd=path)


def set_upstream(branch: str, remote: str = "origin",
                remote_branch: Optional[str] = None, path: Optional[Path] = None):
    """
    Set upstream tracking for a branch.

    Args:
        branch: Local branch name
        remote: Remote name
        remote_branch: Remote branch name (defaults to same as local)
    """
    if remote_branch is None:
        remote_branch = branch

    run_git(["branch", f"--set-upstream-to={remote}/{remote_branch}", branch], cwd=path)


def configure_push_remote(branch: str, remote: str = "origin",
                         remote_branch: Optional[str] = None, path: Optional[Path] = None):
    """
    Configure where a branch should push to, even if remote branch doesn't exist yet.

    This sets branch.{branch}.remote and branch.{branch}.merge so that 'git push'
    will work without needing to specify the remote or use -u flag.

    Args:
        branch: Local branch name
        remote: Remote name
        remote_branch: Remote branch name (defaults to same as local)
        path: Repository path to run git commands in
    """
    if remote_branch is None:
        remote_branch = branch

    # Set the remote
    run_git(["config", f"branch.{branch}.remote", remote], cwd=path)

    # Set the merge target (what the branch tracks/pushes to)
    run_git(["config", f"branch.{branch}.merge", f"refs/heads/{remote_branch}"], cwd=path)


def list_worktrees(path: Optional[Path] = None) -> List[dict]:
    """
    List all worktrees.

    Returns:
        List of dicts with keys: path, branch, commit, locked
    """
    result = run_git(["worktree", "list", "--porcelain"], cwd=path)

    worktrees = []
    current = {}

    for line in result.stdout.strip().split('\n'):
        if not line:
            if current:
                worktrees.append(current)
                current = {}
            continue

        if line.startswith("worktree "):
            current["path"] = Path(line.split(" ", 1)[1])
        elif line.startswith("HEAD "):
            current["commit"] = line.split(" ", 1)[1]
        elif line.startswith("branch "):
            branch = line.split(" ", 1)[1]
            # Remove refs/heads/ prefix
            current["branch"] = branch.replace("refs/heads/", "")
        elif line.startswith("detached"):
            current["branch"] = None
        elif line.startswith("locked"):
            current["locked"] = True

    if current:
        worktrees.append(current)

    return worktrees


def worktree_exists(name: str, path: Optional[Path] = None) -> Tuple[bool, Optional[Path]]:
    """
    Check if a worktree exists by branch name.

    Returns:
        Tuple of (exists, path)
    """
    worktrees = list_worktrees(path)
    for wt in worktrees:
        if wt.get("branch") == name:
            return True, wt["path"]
    return False, None


def add_worktree(path: Path,
                 branch: str,
                 create_branch: bool = False,
                 base: Optional[str] = None,
                 detached: bool = False,
                 repo_path: Optional[Path] = None):
    """
    Create a new worktree.

    Args:
        path: Path where worktree will be created
        branch: Branch name for the worktree
        create_branch: create a new branch instead of using an existing one
        base: Base branch/commit (if None, uses current HEAD)
        detached: Create in detached HEAD state
        repo_path: Path to main repo (for running command)
    """
    args = ["worktree", "add"]

    if detached:
        args.append("--detach")
        args.append(str(path))
        if base:
            args.append(base)
    elif create_branch:
        args.extend(["-b", branch])
        args.append(str(path))
        if base:
            args.append(base)
    else:
        # Use existing branch - format: git worktree add <path> <existing-branch>
        args.append(str(path))
        args.append(branch)

    run_git(args, cwd=repo_path)


def remove_worktree(path: Path, force: bool = False, repo_path: Optional[Path] = None):
    """
    Remove a worktree.

    Args:
        path: Path to the worktree
        force: Force removal even with uncommitted changes
        repo_path: Path to main repo
    """
    args = ["worktree", "remove", str(path)]
    if force:
        args.append("--force")

    run_git(args, cwd=repo_path)


def prune_worktrees(path: Optional[Path] = None):
    """Remove worktree information for deleted directories."""
    run_git(["worktree", "prune"], cwd=path)


def delete_branch(branch: str, force: bool = False, path: Optional[Path] = None):
    """Delete a local branch."""
    flag = "-D" if force else "-d"
    run_git(["branch", flag, branch], cwd=path)


def get_merge_base(branch1: str, branch2: str, path: Optional[Path] = None) -> str:
    """Get the merge base (common ancestor) of two branches."""
    result = run_git(["merge-base", branch1, branch2], cwd=path)
    return result.stdout.strip()


def is_ancestor(ancestor: str, descendant: str, path: Optional[Path] = None) -> bool:
    """Check if ancestor is an ancestor of descendant (i.e., branch is merged)."""
    result = run_git(["merge-base", "--is-ancestor", ancestor, descendant],
                     cwd=path, check=False)
    return result.returncode == 0


def get_upstream_branch(branch: str, path: Optional[Path] = None) -> Optional[str]:
    """Get the upstream tracking branch for a local branch."""
    result = run_git(["rev-parse", "--abbrev-ref", f"{branch}@{{upstream}}"],
                     cwd=path, check=False)
    if result.returncode == 0:
        return result.stdout.strip()
    return None


def get_ahead_behind(branch: str, upstream: str, path: Optional[Path] = None) -> Tuple[int, int]:
    """
    Get how many commits ahead/behind the branch is from upstream.

    Returns:
        Tuple of (ahead, behind)
    """
    result = run_git(["rev-list", "--left-right", "--count", f"{upstream}...{branch}"],
                     cwd=path)
    behind, ahead = result.stdout.strip().split()
    return int(ahead), int(behind)


def diff_trees(tree1: str, tree2: str, path: Optional[Path] = None,
              stat: bool = False, name_only: bool = False) -> str:
    """
    Get diff between two tree-ish objects (commits, branches, etc).

    Args:
        tree1: First tree-ish
        tree2: Second tree-ish
        path: Repo path
        stat: Show diffstat
        name_only: Show only file names

    Returns:
        Diff output
    """
    args = ["diff", tree1, tree2]
    if stat:
        args.append("--stat")
    if name_only:
        args.append("--name-only")

    result = run_git(args, cwd=path)
    return result.stdout


def get_changed_files_in_commit(commit: str = "HEAD", path: Optional[Path] = None) -> str:
    """Get list of files changed in a commit."""
    result = run_git(["show", "--name-status", "--pretty=format:", commit], cwd=path)
    return result.stdout.strip()


def get_default_branch(path: Optional[Path] = None) -> str:
    """
    Get the default branch name (usually main or master).

    First tries to get from origin/HEAD, falls back to common names.
    """
    # Try to get from origin/HEAD
    result = run_git(["symbolic-ref", "refs/remotes/origin/HEAD"], cwd=path, check=False)
    if result.returncode == 0:
        # Output is like "refs/remotes/origin/main"
        return result.stdout.strip().split('/')[-1]

    # Fallback: check common branch names
    for branch in ["main", "master"]:
        if branch_exists(branch, path):
            return branch

    # Last resort: return main
    return "main"
