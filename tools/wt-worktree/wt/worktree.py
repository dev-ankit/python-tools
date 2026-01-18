"""Core worktree operations."""

from pathlib import Path
from typing import Optional, List, Tuple
from . import git
from .config import Config
from .prompts import confirm, error, info, warning

EXIT_ERROR = 1
class WorktreeManager:
    """Manages git worktree operations."""

    def __init__(self, config: Config):
        """
        Initialize worktree manager.

        Args:
            config: Configuration object
        """
        self.config = config
        self.repo_root = config.repo_root

    def list_worktrees(self) -> List[dict]:
        """
        List all worktrees with enhanced information.

        Returns:
            List of worktree dicts with keys: name, path, branch, commit, message
        """
        worktrees = git.list_worktrees(self.repo_root)

        # Enhance with commit messages
        for wt in worktrees:
            try:
                wt["message"] = git.get_commit_message(wt["commit"], self.repo_root)
            except git.GitError:
                wt["message"] = ""

            # Extract worktree name from branch
            if wt.get("branch"):
                wt["name"] = self.config.extract_worktree_name(wt["branch"])
            else:
                wt["name"] = "(detached)"

        return worktrees

    def get_current_worktree(self) -> Optional[dict]:
        """
        Get the current worktree.

        Returns:
            Worktree dict or None
        """
        import os
        cwd = Path(os.getcwd())

        worktrees = self.list_worktrees()
        for wt in worktrees:
            try:
                if cwd.resolve() == wt["path"].resolve() or \
                   cwd.is_relative_to(wt["path"]):
                    return wt
            except (ValueError, OSError):
                # is_relative_to can raise on some systems
                if str(cwd.resolve()).startswith(str(wt["path"].resolve())):
                    return wt

        return None

    def find_worktree_by_name(self, name: str) -> Optional[dict]:
        """
        Find a worktree by name.

        Args:
            name: Worktree name (can be full branch or just suffix)

        Returns:
            Worktree dict or None
        """
        worktrees = self.list_worktrees()

        # Try exact match on name first
        for wt in worktrees:
            if wt.get("name") == name:
                return wt

        # Try matching full branch name
        for wt in worktrees:
            if wt.get("branch") == name:
                return wt

        # Try with prefix
        full_branch = self.config.get_branch_name(name)
        for wt in worktrees:
            if wt.get("branch") == full_branch:
                return wt

        return None

    def get_default_worktree(self) -> Optional[dict]:
        """
        Get the default worktree (main/master).

        Returns:
            Worktree dict or None
        """
        # Check config first
        default_name = self.config.get("default_worktree")
        if default_name:
            return self.find_worktree_by_name(default_name)

        # Auto-detect: find main or master branch
        default_branch = git.get_default_branch(self.repo_root)
        worktrees = self.list_worktrees()

        for wt in worktrees:
            if wt.get("branch") == default_branch:
                return wt

        # Fallback: return first worktree
        if worktrees:
            return worktrees[0]

        return None

    def create_worktree(self, name: str, base: Optional[str] = None,
                       detached: bool = False) -> Path:
        """
        Create a new worktree.

        Args:
            name: Worktree name (suffix)
            base: Base branch/commit
            detached: Create in detached HEAD state

        Returns:
            Path to created worktree

        Raises:
            git.GitError: If creation fails
        """
        # Get full branch name
        branch = self.config.get_branch_name(name)
        create_branch = not git.branch_exists(branch, self.repo_root)

        exists, path = git.worktree_exists(branch, self.repo_root)
        if exists:
            raise git.GitError(
                f"Worktree '{name}' already exists at {path}\n"
                f"Use 'wt switch {name}' to switch to it."
            )

        # Resolve worktree path
        wt_path = self.config.resolve_path_pattern(name, branch)

        # Check if path already exists
        if wt_path.exists():
            raise git.GitError(
                f"Path {wt_path} already exists. "
                f"Please remove it or choose a different name."
            )

        # Determine base branch
        if base is None:
            base = self.config.get("default_base")

        # Create worktree
        try:
            git.add_worktree(wt_path, branch, create_branch, base, detached, self.repo_root)
        except git.GitError as e:
            raise git.GitError(f"Failed to create worktree: {e}")

        # Set upstream tracking if not detached
        if not detached:
            try:
                # Set upstream to origin/<branch>
                remote_branch = branch
                git.set_upstream(branch, "origin", remote_branch, self.repo_root)
            except git.GitError:
                # Upstream setting might fail if remote doesn't exist yet
                # This is okay, user can push later
                pass

        return wt_path

    def delete_worktree(self, name: str, force: bool = False,
                       keep_branch: bool = False) -> bool:
        """
        Delete a worktree.

        Args:
            name: Worktree name
            force: Force deletion without prompts
            keep_branch: Keep the branch after deleting worktree

        Returns:
            True if deleted, False if cancelled

        Raises:
            git.GitError: If deletion fails
        """
        # Find worktree
        wt = self.find_worktree_by_name(name)
        if not wt:
            raise git.GitError(f"Worktree '{name}' not found")

        wt_path = wt["path"]
        branch = wt.get("branch")

        # Check if it's the current worktree
        current = self.get_current_worktree()
        if current and current["path"] == wt_path:
            raise git.GitError(
                "Cannot delete current worktree.\n"
                "Switch to a different worktree first: wt switch ^"
            )

        # Check for uncommitted changes
        if not force and git.has_uncommitted_changes(wt_path):
            status = git.get_status_short(wt_path)
            error(
                f"Worktree '{name}' has uncommitted changes:\n{status}\n"
                "use --force to delete anyway",
                EXIT_ERROR)
            return

        # Check for unpushed commits
        if not force and branch:
            upstream = git.get_upstream_branch(branch, self.repo_root)
            if upstream:
                try:
                    ahead, behind = git.get_ahead_behind(branch, upstream, self.repo_root)
                    if ahead > 0:
                        # Get list of unpushed commits
                        result = git.run_git(
                            ["log", "--oneline", f"{upstream}..{branch}"],
                            cwd=self.repo_root
                        )
                        commits = result.stdout.strip()

                        if not confirm(
                            f"Worktree '{name}' has {ahead} unpushed commit(s):\n{commits}\n\n"
                            "Delete anyway?",
                            default=False
                        ):
                            return False
                except git.GitError:
                    # Upstream comparison failed, continue
                    pass

        # Remove worktree
        try:
            git.remove_worktree(wt_path, force=force, repo_path=self.repo_root)
        except git.GitError as e:
            raise git.GitError(f"Failed to remove worktree: {e}")

        # Delete branch unless --keep-branch
        if not keep_branch and branch:
            try:
                git.delete_branch(branch, force=force, path=self.repo_root)
            except git.GitError as e:
                warning(f"Worktree removed but failed to delete branch: {e}")

        # Prune worktree info
        git.prune_worktrees(self.repo_root)

        return True

    def get_worktree_status(self, wt: dict) -> dict:
        """
        Get detailed status for a worktree.

        Args:
            wt: Worktree dict

        Returns:
            Status dict with keys: uncommitted_count, uncommitted_files, ahead, behind, upstream
        """
        wt_path = wt["path"]
        branch = wt.get("branch")

        status = {
            "uncommitted_count": 0,
            "uncommitted_files": "",
            "ahead": 0,
            "behind": 0,
            "upstream": None,
        }

        # Check uncommitted changes
        if git.has_uncommitted_changes(wt_path):
            files = git.get_status_short(wt_path)
            status["uncommitted_files"] = files
            status["uncommitted_count"] = len(files.strip().split('\n'))

        # Check ahead/behind status
        if branch:
            upstream = git.get_upstream_branch(branch, self.repo_root)
            status["upstream"] = upstream

            if upstream:
                try:
                    ahead, behind = git.get_ahead_behind(branch, upstream, self.repo_root)
                    status["ahead"] = ahead
                    status["behind"] = behind
                except git.GitError:
                    pass

        return status

    def clean_merged_worktrees(self, dry_run: bool = False, force: bool = False) -> List[str]:
        """
        Remove worktrees for merged or deleted branches.

        Args:
            dry_run: Only show what would be deleted
            force: Skip confirmation prompts

        Returns:
            List of removed worktree names
        """
        worktrees = self.list_worktrees()
        default_branch = git.get_default_branch(self.repo_root)
        to_remove = []

        for wt in worktrees:
            branch = wt.get("branch")
            if not branch:
                continue

            # Skip default branch and non-prefixed branches
            if branch == default_branch:
                continue

            # Skip if doesn't match our prefix
            name = wt.get("name")
            if name == branch:  # No prefix was stripped
                continue

            # Check if merged into default branch
            try:
                if git.is_ancestor(branch, f"origin/{default_branch}", self.repo_root):
                    to_remove.append((name, "merged into " + default_branch))
                    continue
            except git.GitError:
                pass

            # Check if remote branch was deleted
            upstream = git.get_upstream_branch(branch, self.repo_root)
            if upstream:
                # Parse remote name from upstream (e.g., "origin/feature/foo" -> "origin", "feature/foo")
                remote = upstream.split('/')[0]
                remote_branch = '/'.join(upstream.split('/')[1:])

                if not git.remote_branch_exists(remote_branch, remote, self.repo_root):
                    to_remove.append((name, "remote branch deleted"))

        if not to_remove:
            info("No worktrees to clean")
            return []

        # Show what will be removed
        if dry_run or not force:
            info("The following worktrees will be removed:")
            for name, reason in to_remove:
                info(f"  {name:20} ({reason})")

        if dry_run:
            return [name for name, _ in to_remove]

        # Confirm
        if not force:
            if not confirm("\nProceed?", default=False):
                return []

        # Remove worktrees
        removed = []
        for name, reason in to_remove:
            try:
                if self.delete_worktree(name, force=True, keep_branch=False):
                    info(f"Removed {name} ({reason})")
                    removed.append(name)
            except git.GitError as e:
                warning(f"Failed to remove {name}: {e}")

        return removed
