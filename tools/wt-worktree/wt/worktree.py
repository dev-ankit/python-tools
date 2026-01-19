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

    def _infer_name_from_path(self, wt_path: Path) -> Optional[str]:
        """
        Try to infer worktree name from its path based on path_pattern.

        Provides backward compatibility for detached worktrees created before
        the name-storing feature was added.

        Args:
            wt_path: Path to the worktree

        Returns:
            Inferred name or None
        """
        # Get the pattern and try common formats
        pattern = self.config.get("path_pattern")
        repo_name = self.repo_root.name

        # Try pattern: ../{repo}-{name}
        if pattern == "../{repo}-{name}":
            expected_prefix = f"{repo_name}-"
            if wt_path.name.startswith(expected_prefix):
                return wt_path.name[len(expected_prefix):]

        # Try pattern: ../{name}
        elif pattern == "../{name}":
            # Exclude the main worktree
            if wt_path != self.repo_root:
                return wt_path.name

        return None

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

            # Extract worktree name from branch or config
            if wt.get("branch"):
                wt["name"] = self.config.extract_worktree_name(wt["branch"])
            else:
                # For detached worktrees, try multiple sources
                stored_name = git.get_worktree_name(wt["path"])
                if stored_name:
                    wt["name"] = stored_name
                else:
                    # Try to infer from path (backward compatibility)
                    inferred_name = self._infer_name_from_path(wt["path"])
                    if inferred_name:
                        wt["name"] = inferred_name
                    else:
                        # Fallback: use commit hash as identifier
                        wt["name"] = f"(detached-{wt['commit'][:7]})"

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

        # Try exact match on name first (works for both regular and detached worktrees)
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
            # For detached worktrees, use HEAD by default (not default_base)
            # default_base is meant for creating new branches, not detached worktrees
            if detached:
                base = "HEAD"
            else:
                base = self.config.get("default_base")

        # Create worktree
        try:
            git.add_worktree(wt_path, branch, create_branch, base, detached, self.repo_root)
        except git.GitError as e:
            raise git.GitError(f"Failed to create worktree: {e}")

        # Store worktree name in config if detached (so we can find it later)
        if detached:
            git.set_worktree_name(name, wt_path)

        # Configure push remote if not detached
        if not detached and create_branch:
            try:
                # For new branches, configure where to push (so git push works without -u)
                # This works even if remote branch doesn't exist yet
                git.configure_push_remote(branch, "origin", branch, wt_path)
            except git.GitError:
                # If this fails, user can still push with -u flag
                pass
        elif not detached:
            try:
                # For existing branches, check if remote branch exists and set upstream
                if git.remote_branch_exists(branch, "origin", self.repo_root):
                    git.set_upstream(branch, "origin", branch, self.repo_root)
                else:
                    # Remote doesn't exist yet, configure push target instead
                    git.configure_push_remote(branch, "origin", branch, wt_path)
            except git.GitError:
                # If this fails, user can still push with -u flag
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

    def sync_worktree(self, wt: dict, rebase: bool = False) -> dict:
        """
        Sync a single worktree with its upstream branch.

        Args:
            wt: Worktree dict
            rebase: Rebase onto default base after pull

        Returns:
            Dict with keys: success, stashed, message, error
        """
        wt_path = wt["path"]
        wt_name = wt["name"]
        branch = wt.get("branch")

        result = {
            "success": False,
            "stashed": False,
            "message": "",
            "error": None,
        }

        # Skip if detached HEAD
        if not branch:
            result["error"] = "detached HEAD, skipping"
            return result

        # Get upstream branch
        upstream = git.get_upstream_branch(branch, self.repo_root)
        if not upstream:
            result["error"] = "no upstream branch"
            return result

        # Parse remote from upstream (e.g., "origin/feature/foo" -> "origin", "feature/foo")
        remote_parts = upstream.split('/', 1)
        if len(remote_parts) < 2:
            result["error"] = f"invalid upstream: {upstream}"
            return result

        remote = remote_parts[0]
        remote_branch = remote_parts[1]

        # Step 1: Stash uncommitted changes if any
        if git.has_uncommitted_changes(wt_path):
            info(f"[{wt_name}] Stashing uncommitted changes...")
            if git.stash_changes(wt_path):
                result["stashed"] = True
            else:
                result["error"] = "failed to stash changes"
                return result

        try:
            # Step 2: Pull from upstream
            info(f"[{wt_name}] Pulling from {upstream}...")
            pull_success, pull_msg = git.pull_branch(remote_branch, wt_path, remote)

            if not pull_success:
                result["error"] = f"pull {pull_msg}"
                return result

            # Update message based on pull result
            if pull_msg == "already_up_to_date":
                result["message"] = "✓ Already up to date"
            elif pull_msg == "fast_forward":
                # Count commits
                try:
                    ahead, _ = git.get_ahead_behind(branch, upstream, self.repo_root)
                    result["message"] = f"✓ Fast-forward: {ahead} commits"
                except git.GitError:
                    result["message"] = "✓ Fast-forward"
            else:
                result["message"] = "✓ Merged: 1 commit"

            # Step 3: Rebase onto default base if requested
            if rebase:
                default_base = self.config.get("default_base")
                if not default_base:
                    default_base = "origin/main"

                info(f"[{wt_name}] Rebasing onto {default_base}...")
                rebase_success, rebase_msg = git.rebase_branch(branch, default_base, wt_path)

                if not rebase_success:
                    result["error"] = f"rebase {rebase_msg}"
                    return result

                # Update message
                if rebase_msg == "up_to_date":
                    result["message"] += "\n✓ Already based on " + default_base
                else:
                    # Count commits ahead of base
                    try:
                        ahead, _ = git.get_ahead_behind(branch, default_base, self.repo_root)
                        result["message"] += f"\n✓ Rebased, {ahead} commits ahead"
                    except git.GitError:
                        result["message"] += "\n✓ Rebased"

            result["success"] = True

        finally:
            # Step 4: Pop stash if we stashed earlier
            if result["stashed"]:
                info(f"[{wt_name}] Restoring uncommitted changes...")
                if git.stash_pop(wt_path):
                    result["message"] += "\n✓ Stash applied"
                else:
                    # If pop failed, it might be due to conflicts
                    # Leave it in the stash for user to handle
                    warning(f"[{wt_name}] Failed to apply stash, preserved in stash@{{0}}")
                    if result["success"]:
                        result["error"] = "stash conflict"
                        result["success"] = False

        return result

    def sync_worktrees(self, worktree_names: Optional[List[str]] = None,
                      rebase: bool = False) -> Tuple[List[dict], List[dict]]:
        """
        Sync multiple worktrees with their upstream branches.

        Args:
            worktree_names: List of worktree names to sync (None = current worktree only)
            rebase: Rebase onto default base after pull

        Returns:
            Tuple of (succeeded, failed) where each is a list of dicts with keys:
            name, message (for succeeded) or name, error, stashed (for failed)
        """
        # Determine which worktrees to sync
        all_worktrees = self.list_worktrees()

        if worktree_names is None:
            # Sync current worktree only
            current = self.get_current_worktree()
            if not current:
                raise git.GitError("Cannot determine current worktree")
            worktrees_to_sync = [current]
        else:
            # Find specified worktrees
            worktrees_to_sync = []
            for name in worktree_names:
                wt = self.find_worktree_by_name(name)
                if wt:
                    worktrees_to_sync.append(wt)
                else:
                    warning(f"Worktree '{name}' not found, skipping")

        if not worktrees_to_sync:
            raise git.GitError("No worktrees to sync")

        info(f"Syncing {len(worktrees_to_sync)} worktree(s)...\n")

        succeeded = []
        failed = []

        for wt in worktrees_to_sync:
            wt_name = wt["name"]
            result = self.sync_worktree(wt, rebase)

            if result["success"]:
                succeeded.append({
                    "name": wt_name,
                    "message": result["message"]
                })
                # Print success message
                for line in result["message"].split('\n'):
                    if line:
                        info(f"[{wt_name}] {line}")
            else:
                failed.append({
                    "name": wt_name,
                    "error": result["error"],
                    "stashed": result.get("stashed", False)
                })
                # Print error message (without exiting)
                error_msg = result["error"]
                if "conflict" in error_msg:
                    warning(f"[{wt_name}] ✗ {error_msg.capitalize()}")
                    info(f"[{wt_name}] Skipping, resolve manually")
                else:
                    warning(f"[{wt_name}] ✗ {error_msg}")

            print()  # Empty line between worktrees

        return succeeded, failed
