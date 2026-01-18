"""CLI commands for wt."""

import os
import sys
import subprocess
from pathlib import Path
from typing import Optional

import click

from . import git
from .config import Config, ConfigError
from .worktree import WorktreeManager
from .prompts import confirm, error, info, success, warning
from .shell import generate_shell_init, get_supported_shells


# Exit codes
EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_INVALID_ARGS = 2
EXIT_GIT_ERROR = 3
EXIT_NOT_FOUND = 4
EXIT_CANCELLED = 5


# Context object to pass between commands
class Context:
    def __init__(self):
        self.config: Optional[Config] = None
        self.manager: Optional[WorktreeManager] = None
        self.repo_root: Optional[Path] = None
        self.previous_worktree_file: Optional[Path] = None


pass_context = click.make_pass_decorator(Context, ensure=True)


@click.group()
@click.version_option(version="0.1.0", prog_name="wt")
@pass_context
def cli(ctx: Context):
    """Git worktree manager for parallel development workflows."""
    # Try to find repo root
    try:
        if git.is_git_repo():
            # Use main worktree root for config (important when running from secondary worktrees)
            ctx.repo_root = git.get_main_worktree_root()
            ctx.config = Config(ctx.repo_root)
            ctx.manager = WorktreeManager(ctx.config)

            # Track previous worktree
            ctx.previous_worktree_file = ctx.repo_root / ".git" / ".wt_previous"
    except git.GitError:
        # Not in a repo - some commands don't need it
        pass


@cli.command()
@click.option("--prefix", default="feature", help="Branch prefix for new worktrees")
@click.option("--path", "path_pattern", default="../{repo}-{name}",
              help="Path pattern for worktree directories")
@pass_context
def init(ctx: Context, prefix: str, path_pattern: str):
    """Create or update wt configuration with custom defaults."""
    # Create configuration with provided values
    config_data = {
        "prefix": prefix,
        "path_pattern": path_pattern,
        "default_base": "origin/main",
        "default_worktree": None,
    }

    config = Config()
    try:
        config.save(config_data)
        config_path = config.get_config_path()
        success(f"Configuration saved to {config_path}")
        info(f"\nBranch prefix: {prefix}")
        info(f"Path pattern: {path_pattern}")
        info("\nConfiguration will be used for all repositories.")
    except ConfigError as e:
        error(str(e), EXIT_ERROR)


@cli.command()
@click.argument("name", required=False)
@click.option("-c", "--create", is_flag=True, help="Create worktree if it doesn't exist")
@click.option("-b", "--base", help="Base branch for new worktree")
@click.option("-d", "--detached", is_flag=True, help="Create in detached HEAD state")
@click.option("--shell-helper", is_flag=True, hidden=True,
              help="Internal flag for shell integration")
@pass_context
def switch(ctx: Context, name: Optional[str], create: bool, base: Optional[str],
          detached: bool, shell_helper: bool):
    """Switch to a worktree, optionally creating it."""
    if not ctx.repo_root or not ctx.manager:
        error("Not in a git repository.", EXIT_GIT_ERROR)
        return

    # Handle special names
    if name == "-":
        # Switch to previous worktree
        if not ctx.previous_worktree_file.exists():
            error("No previous worktree", EXIT_ERROR)
            return

        prev_path = ctx.previous_worktree_file.read_text().strip()
        if not Path(prev_path).exists():
            error(f"Previous worktree no longer exists: {prev_path}", EXIT_NOT_FOUND)
            return

        name = None
        # Find worktree by path
        for wt in ctx.manager.list_worktrees():
            if str(wt["path"]) == prev_path:
                name = wt["name"]
                break

        if not name:
            error("Previous worktree not found", EXIT_NOT_FOUND)
            return

    elif name == "^":
        # Switch to default worktree
        default_wt = ctx.manager.get_default_worktree()
        if not default_wt:
            error("Cannot determine default worktree", EXIT_ERROR)
            return
        name = default_wt["name"]

    if not name:
        error("Worktree name required", EXIT_INVALID_ARGS)
        return

    # Check if worktree exists
    target_wt = ctx.manager.find_worktree_by_name(name)

    if target_wt:
        # Worktree exists - switch to it
        current_wt = ctx.manager.get_current_worktree()

        # Record current worktree as previous
        if current_wt:
            ctx.previous_worktree_file.write_text(str(current_wt["path"]))

        # Output path for shell integration
        if shell_helper:
            print(target_wt["path"])
        else:
            success(f"To switch to worktree '{name}' run: cd {target_wt['path']}")

    elif create:
        # Create new worktree
        try:
            # Check if branch exists
            full_branch = ctx.config.get_branch_name(name)

            # Create worktree
            wt_path = ctx.manager.create_worktree(name, base, detached)

            # Record current worktree as previous
            current_wt = ctx.manager.get_current_worktree()
            if current_wt:
                ctx.previous_worktree_file.write_text(str(current_wt["path"]))

            # Output path for shell integration
            if shell_helper:
                print(wt_path)
            else:
                success(f"To switch to worktree '{name}' run: cd {wt_path}")

        except git.GitError as e:
            error(str(e), EXIT_GIT_ERROR)

    else:
        # Worktree doesn't exist and --create not specified
        available = [wt["name"] for wt in ctx.manager.list_worktrees()]
        error(
            f"Worktree '{name}' not found\n"
            f"Available worktrees: {', '.join(available)}\n"
            f"Use 'wt switch -c {name}' to create it.",
            EXIT_NOT_FOUND
        )


@cli.command("list")
@click.option("--name-only", is_flag=True, help="Show changed files from last commit")
@pass_context
def list_cmd(ctx: Context, name_only: bool):
    """List all worktrees with their status."""
    if not ctx.repo_root or not ctx.manager:
        error("Not in a git repository", EXIT_GIT_ERROR)
        return

    worktrees = ctx.manager.list_worktrees()
    current_wt = ctx.manager.get_current_worktree()
    current_path = current_wt["path"] if current_wt else None

    if name_only:
        # Show changed files in last commit for each worktree
        for wt in worktrees:
            commit = wt["commit"]
            name = wt["name"]

            print(f"{name} ({commit[:7]}):")

            try:
                changed = git.get_changed_files_in_commit(commit, wt["path"])
                if changed:
                    for line in changed.strip().split('\n'):
                        if line:
                            print(f"  {line}")
                else:
                    print("  (no changes)")
            except git.GitError:
                print("  (error reading commit)")

            print()
    else:
        # Standard list format
        for wt in worktrees:
            path = wt["path"]
            name = wt["name"]
            commit = wt["commit"][:7]
            message = wt.get("message", "")

            # Truncate message if too long
            if len(message) > 50:
                message = message[:47] + "..."

            # Mark current worktree
            marker = "*" if path == current_path else " "

            print(f"{marker} {name:20} {commit}  {message:50}  {path}")


@cli.command()
@click.argument("worktree")
@click.argument("base", required=False)
@click.argument("diff_args", nargs=-1)
@pass_context
def diff(ctx: Context, worktree: str, base: Optional[str], diff_args: tuple):
    """Compare committed changes between worktrees."""
    if not ctx.repo_root or not ctx.manager:
        error("Not in a git repository", EXIT_GIT_ERROR)
        return

    # Find target worktree
    target_wt = ctx.manager.find_worktree_by_name(worktree)
    if not target_wt:
        error(f"Worktree '{worktree}' not found", EXIT_NOT_FOUND)
        return

    # Determine base worktree
    if base:
        base_wt = ctx.manager.find_worktree_by_name(base)
        if not base_wt:
            error(f"Worktree '{base}' not found", EXIT_NOT_FOUND)
            return
    else:
        # Use current worktree as base
        base_wt = ctx.manager.get_current_worktree()
        if not base_wt:
            error("Cannot determine current worktree", EXIT_ERROR)
            return

    # Get branch names
    base_branch = base_wt.get("branch") or base_wt["commit"]
    target_branch = target_wt.get("branch") or target_wt["commit"]

    # Run git diff
    try:
        args = ["diff", base_branch, target_branch] + list(diff_args)
        result = git.run_git(args, cwd=ctx.repo_root, capture_output=False)
        sys.exit(result.returncode)
    except git.GitError as e:
        error(str(e), EXIT_GIT_ERROR)


@cli.command()
@click.argument("name")
@click.option("--force", is_flag=True, help="Delete without prompts")
@click.option("--keep-branch", is_flag=True, help="Keep branch after deleting worktree")
@pass_context
def delete(ctx: Context, name: str, force: bool, keep_branch: bool):
    """Delete a worktree and optionally its branch."""
    if not ctx.repo_root or not ctx.manager:
        error("Not in a git repository", EXIT_GIT_ERROR)
        return

    try:
        deleted = ctx.manager.delete_worktree(name, force, keep_branch)
        if deleted:
            success(f"Deleted worktree '{name}'")
        else:
            sys.exit(EXIT_CANCELLED)
    except git.GitError as e:
        error(str(e), EXIT_GIT_ERROR)


@cli.command()
@pass_context
def status(ctx: Context):
    """Show status of all worktrees."""
    if not ctx.repo_root or not ctx.manager:
        error("Not in a git repository", EXIT_GIT_ERROR)
        return

    worktrees = ctx.manager.list_worktrees()

    for wt in worktrees:
        name = wt["name"]
        commit = wt["commit"][:7]
        st = ctx.manager.get_worktree_status(wt)

        # Status line
        if st["uncommitted_count"] > 0:
            status_str = f"{st['uncommitted_count']} uncommitted changes"
        else:
            status_str = "clean"

        print(f"{name} ({commit}) - {status_str}")

        # Show uncommitted files
        if st["uncommitted_files"]:
            for line in st["uncommitted_files"].strip().split('\n')[:5]:
                print(f"  {line}")
            if st["uncommitted_count"] > 5:
                print(f"  ... and {st['uncommitted_count'] - 5} more")

        # Show ahead/behind status
        if st["upstream"]:
            ahead = st["ahead"]
            behind = st["behind"]

            if ahead == 0 and behind == 0:
                print(f"  ✓ up to date with {st['upstream']}")
            else:
                parts = []
                if ahead > 0:
                    parts.append(f"↑{ahead}")
                if behind > 0:
                    parts.append(f"↓{behind}")
                print(f"  {' '.join(parts)} {st['upstream']}")
        elif wt.get("branch"):
            print(f"  (no upstream)")

        print()


@cli.command()
@click.argument("name")
@click.argument("command")
@pass_context
def run(ctx: Context, name: str, command: str):
    """Run a command in a specific worktree."""
    if not ctx.repo_root or not ctx.manager:
        error("Not in a git repository", EXIT_GIT_ERROR)
        return

    # Handle special names
    if name == "-":
        # Use previous worktree
        if not ctx.previous_worktree_file.exists():
            error("No previous worktree", EXIT_ERROR)
            return

        prev_path = ctx.previous_worktree_file.read_text().strip()
        if not Path(prev_path).exists():
            error(f"Previous worktree no longer exists: {prev_path}", EXIT_NOT_FOUND)
            return

        # Find worktree by path
        found_name = None
        for wt in ctx.manager.list_worktrees():
            if str(wt["path"]) == prev_path:
                found_name = wt["name"]
                break

        if not found_name:
            error("Previous worktree not found", EXIT_NOT_FOUND)
            return
        name = found_name

    elif name == "^":
        # Use default worktree
        default_wt = ctx.manager.get_default_worktree()
        if not default_wt:
            error("Cannot determine default worktree", EXIT_ERROR)
            return
        name = default_wt["name"]

    # Find worktree
    wt = ctx.manager.find_worktree_by_name(name)
    if not wt:
        error(f"Worktree '{name}' not found", EXIT_NOT_FOUND)
        return

    wt_path = wt["path"]

    # Run command
    try:
        result = subprocess.run(
            command,
            cwd=wt_path,
            shell=True
        )
        sys.exit(result.returncode)
    except Exception as e:
        error(f"Failed to run command: {e}", EXIT_ERROR)


@cli.command()
@click.option("--dry-run", is_flag=True, help="Show what would be deleted")
@click.option("--force", is_flag=True, help="Skip confirmation prompts")
@pass_context
def clean(ctx: Context, dry_run: bool, force: bool):
    """Remove worktrees for merged or deleted branches."""
    if not ctx.repo_root or not ctx.manager:
        error("Not in a git repository", EXIT_GIT_ERROR)
        return

    try:
        removed = ctx.manager.clean_merged_worktrees(dry_run, force)
        if not dry_run and removed:
            success(f"Removed {len(removed)} worktree(s)")
    except git.GitError as e:
        error(str(e), EXIT_GIT_ERROR)


@cli.command()
@click.argument("key", required=False)
@click.argument("value", required=False)
@click.option("--list", "list_all", is_flag=True, help="Show all configuration")
@click.option("--edit", is_flag=True, help="Open config file in $EDITOR")
@pass_context
def config(ctx: Context, key: Optional[str], value: Optional[str],
          list_all: bool, edit: bool):
    """View or modify configuration."""
    if not ctx.config:
        ctx.config = Config(None)

    if edit:
        # Open config in editor
        config_path = ctx.config.get_config_path()

        # Create file if it doesn't exist
        if not config_path.exists():
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.touch()

        # Open in editor
        editor = os.environ.get("EDITOR", "vi")
        subprocess.run([editor, str(config_path)])
        return

    if list_all:
        # Show all config
        all_config = ctx.config.get_all()
        config_path = ctx.config.get_config_path()
        info(f"Config file: {config_path}\n")
        for k, v in all_config.items():
            print(f"{k} = {v}")
        return

    if key and value:
        # Set config value
        try:
            ctx.config.set(key, value)
            ctx.config.save()
            success(f"Set config: {key} = {value}")
            info(f"Saved to {ctx.config.get_config_path()}")
        except (ConfigError, ValueError) as e:
            error(str(e), EXIT_ERROR)

    elif key:
        # Get config value
        val = ctx.config.get(key)
        if val is not None:
            print(val)
        else:
            error(f"Unknown config key: {key}", EXIT_ERROR)

    else:
        # No args - show usage
        click.echo(click.get_current_context().get_help())


@cli.command("shell-init")
@click.argument("shell", type=click.Choice(get_supported_shells()))
def shell_init(shell: str):
    """Output shell integration code."""
    try:
        code = generate_shell_init(shell)
        print(code)
    except ValueError as e:
        error(str(e), EXIT_INVALID_ARGS)


def main():
    """Main entry point."""
    try:
        cli()
    except KeyboardInterrupt:
        print("\nCancelled", file=sys.stderr)
        sys.exit(EXIT_CANCELLED)
    except Exception as e:
        error(f"Unexpected error: {e}", EXIT_ERROR)


if __name__ == "__main__":
    main()
