# `wt` - Git Worktree Manager for Agentic Workflows

`wt` is a CLI tool that simplifies git worktree management, enabling parallel development workflows where multiple agents (or developers) can work on separate features simultaneously. It provides an intuitive interface for creating, switching, and managing worktrees with sensible defaults and shell integration for seamless directory navigation.

## Features

- **Simple worktree management**: Create, switch, list, and delete worktrees with intuitive commands
- **Smart defaults**: Configurable branch prefixes and path patterns
- **Shell integration**: Seamless `cd` support for bash, zsh, and fish
- **Status tracking**: View uncommitted changes and sync status across all worktrees
- **Auto-cleanup**: Remove merged or deleted worktrees automatically
- **Parallel workflows**: Perfect for multi-agent development environments

## Installation

```bash
# Install from GitHub
uv tool install 'git+https://github.com/dev-ankit/python-tools.git#subdirectory=tools/wt-worktree'

# Or install locally
git clone https://github.com/dev-ankit/python-tools.git
cd python-tools/tools/wt-worktree
uv pip install -e .
```

### Shell Integration

After installation, add shell integration to your shell config:

```bash
# For bash (~/.bashrc)
eval "$(wt shell-init bash)"

# For zsh (~/.zshrc)
eval "$(wt shell-init zsh)"

# For fish (~/.config/fish/config.fish)
wt shell-init fish | source
```

## Quick Start

```bash
# Create and switch to a new feature worktree (no initialization needed!)
wt switch -c my-feature

# List all worktrees
wt list

# Switch back to previous worktree
wt switch -

# Switch to default (main) worktree
wt switch ^

# Run a command in a specific worktree
wt run my-feature "pytest"

# Compare changes between worktrees
wt diff my-feature

# Clean up merged worktrees
wt clean

# Optional: Customize configuration
wt init --prefix dev --path "../{name}"
```

## Commands

### `wt init` (Optional)

Create or update `wt` configuration with custom defaults. Configuration is stored globally and applies to all repositories.

**Note:** This command is optional! `wt` works with sensible defaults out of the box.

```bash
wt init [--prefix <prefix>] [--path <pattern>]
```

**Options:**
- `--prefix`: Branch prefix for new worktrees (default: `feature`)
- `--path`: Path pattern for worktree directories (default: `../{repo}-{name}`)

**Examples:**

```bash
# Set custom prefix for all repositories
wt init --prefix "dev"  # Creates branches like dev/feat

# Set custom path pattern
wt init --path "../worktrees/{name}"

# Set both
wt init --prefix "wt" --path "../{name}"
```

Configuration is saved to `~/.wt.toml` (or `$WT_CONFIG/.wt.toml` if set).

### `wt switch`

Switch to a worktree, optionally creating it.

```bash
wt switch <name>                    # Switch to existing worktree
wt switch -c <name>                 # Create and switch
wt switch -c <name> -b <base>       # Create from specific base
wt switch -                         # Switch to previous worktree
wt switch ^                         # Switch to default worktree
```

**Examples:**

```bash
# Switch to existing worktree
wt switch feat

# Create new worktree from origin/main
wt switch -c feat

# Create from specific base branch
wt switch -c hotfix -b origin/release-1.0

# Toggle between worktrees
wt switch feat
wt switch other
wt switch -  # Back to feat

# Return to main worktree
wt switch ^
```

### `wt list`

List all worktrees with their status.

```bash
wt list [--name-only]
```

**Output:**

```
  main        abc1234  "Initial commit"           /path/to/repo
* feat        def5678  "Add user authentication"  /path/to/repo-feat
  bugfix      789abcd  "Fix login redirect"       /path/to/repo-bugfix
```

### `wt diff`

Compare committed changes between worktrees.

```bash
wt diff <worktree> [<base>]
```

**Examples:**

```bash
# Compare feat worktree against current worktree
wt diff feat

# Compare feat against main
wt diff feat main

# With diff options
wt diff feat --stat
wt diff feat --name-only
```

### `wt delete`

Delete a worktree and optionally its branch.

```bash
wt delete <name> [--force] [--keep-branch]
```

**Examples:**

```bash
# Delete worktree (prompts for confirmation if needed)
wt delete feat

# Force delete without prompts
wt delete feat --force

# Delete worktree but keep branch
wt delete feat --keep-branch
```

### `wt status`

Show status of all worktrees at once.

```bash
wt status
```

**Output:**

```
main (abc1234) - clean
  ✓ up to date with origin/main

feat (def5678) - 3 uncommitted changes
  M src/auth.py
  M src/models/user.py
  ? debug.log
  ↑1 ↓2 origin/feature/feat
```

### `wt run`

Run a command in a specific worktree.

```bash
wt run <name> <command>
```

**Examples:**

```bash
# Run tests in a worktree
wt run feat "pytest"

# Check git status
wt run feat "git status"

# Start a dev server
wt run feat "uvicorn main:app --reload"
```

### `wt clean`

Remove worktrees for merged or deleted branches.

```bash
wt clean [--dry-run] [--force]
```

**Examples:**

```bash
# Preview what would be cleaned
wt clean --dry-run

# Clean with confirmation
wt clean

# Clean without prompts
wt clean --force
```

### `wt config`

View or modify configuration.

```bash
wt config [<key>] [<value>]
wt config --list
wt config --edit
```

**Examples:**

```bash
# View all config (shows config file location)
wt config --list

# Get specific value
wt config prefix

# Set config value
wt config prefix "dev"

# Open in editor
wt config --edit
```

## Configuration

Configuration is stored in a single TOML file:
- Default location: `~/.wt.toml`
- Custom location: Set `WT_CONFIG` environment variable to a directory

**Example:** `export WT_CONFIG=/path/to/config/dir` → config saved to `/path/to/config/dir/.wt.toml`

### Config File Format

```toml
# Branch prefix for new worktrees
# Branches created as: <prefix>/<name>
prefix = "feature"

# Path pattern for worktree directories
# Variables: {repo}, {name}, {branch}
path_pattern = "../{repo}-{name}"

# Default base branch for new worktrees
default_base = "origin/main"

# Default worktree for `wt switch ^`
# Auto-detected if not set (usually main)
default_worktree = "main"
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `WT_CONFIG` | Directory for config file (defaults to `~`) |
| `WT_NO_PROMPT` | Set to `1` to auto-accept all prompts (for scripting) |

## Use Cases

### Agentic Parallel Development

Multiple AI agents can work on different features simultaneously:

```bash
# Terminal 1: Agent working on auth
wt switch -c auth
# AI agent implements authentication...

# Terminal 2: Agent working on API
wt switch -c api
# AI agent builds API endpoints...

# Terminal 3: Human reviewing both
wt status
wt diff auth
wt diff api
```

### Quick Context Switching

```bash
# Working on feature, need to check something in main
wt switch ^
# ... investigate ...
wt switch -  # Back to feature
```

### Comparing Implementations

```bash
# Two approaches to the same problem
wt switch -c approach-a
# ... implement ...

wt switch -c approach-b
# ... implement differently ...

wt diff approach-a approach-b
```

### Cleanup After Sprint

```bash
# Remove all merged feature branches
wt clean
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments |
| 3 | Git error (not a repo, worktree operation failed) |
| 4 | Worktree not found |
| 5 | User cancelled (prompt declined) |

## Requirements

- Python 3.10+
- Git 2.15+ (for worktree support)
- Click 8.0+

## Development

```bash
# Clone and setup
git clone https://github.com/dev-ankit/python-tools.git
cd python-tools/tools/wt-worktree

# Create virtual environment and install dev dependencies
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=wt --cov-report=term-missing
```

## License

MIT License - see [LICENSE](../../LICENSE) for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Author

Ankit ([@dev-ankit](https://github.com/dev-ankit))
