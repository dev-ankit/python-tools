# `wt` - Git Worktree Manager - Product Requirements Document

## Overview

`wt` is a CLI tool that simplifies git worktree management for parallel development workflows. It enables multiple agents or developers to work on separate features simultaneously with an intuitive interface and shell integration.

## Stories and Tasks

### Story 1: Core Infrastructure ✅
**As a developer, I want the basic project structure and core git operations, so that I can build features on top**

- [x] Task 1.1: Set up project structure with pyproject.toml
- [x] Task 1.2: Implement git operations module (git.py)
- [x] Task 1.3: Implement configuration management (config.py)
- [x] Task 1.4: Implement core worktree operations (worktree.py)
- [x] Task 1.5: Add tests for core modules

### Story 2: Basic Commands ✅
**As a user, I want to initialize and manage worktrees, so that I can work on multiple features**

- [x] Task 2.1: Implement `wt init` command
- [x] Task 2.2: Implement `wt switch` command (existing worktrees)
- [x] Task 2.3: Implement `wt switch -c` (create new worktrees)
- [x] Task 2.4: Implement `wt list` command
- [x] Task 2.5: Add tests for basic commands

### Story 3: Worktree Management Commands ✅
**As a user, I want to compare, delete, and check status of worktrees**

- [x] Task 3.1: Implement `wt diff` command
- [x] Task 3.2: Implement `wt delete` command with prompts
- [x] Task 3.3: Implement `wt status` command
- [x] Task 3.4: Add tests for management commands

### Story 4: Advanced Features ✅
**As a user, I want to run commands in worktrees and clean up merged branches**

- [x] Task 4.1: Implement `wt run` command
- [x] Task 4.2: Implement `wt clean` command
- [x] Task 4.3: Implement `wt config` command
- [x] Task 4.4: Add tests for advanced features

### Story 5: Shell Integration ✅
**As a user, I want seamless shell integration, so that I can navigate worktrees easily**

- [x] Task 5.1: Implement `wt shell-init` command
- [x] Task 5.2: Generate bash/zsh shell wrapper
- [x] Task 5.3: Generate fish shell wrapper
- [x] Task 5.4: Add --shell-helper flag for cd support
- [x] Task 5.5: Test shell integration

### Story 6: User Experience ✅
**As a user, I want helpful prompts and error messages**

- [x] Task 6.1: Implement user prompts module (prompts.py)
- [x] Task 6.2: Add comprehensive error messages
- [x] Task 6.3: Add progress indicators
- [x] Task 6.4: Handle edge cases (spaces in paths, special characters)

### Story 7: Documentation and Testing ✅
**As a developer, I want comprehensive documentation and tests**

- [x] Task 7.1: Write comprehensive test suite
- [x] Task 7.2: Create README.md with usage examples
- [x] Task 7.3: Create notes.md documenting implementation decisions
- [x] Task 7.4: Update root README.md
- [x] Task 7.5: End-to-end testing

## Success Criteria

1. All commands work as specified in the spec
2. Test coverage > 80%
3. Shell integration works in bash, zsh, and fish
4. Error messages are clear and actionable
5. Configuration system works with both local and global configs
6. Tool handles edge cases gracefully (uncommitted changes, conflicts, etc.)

## Technical Requirements

- Python 3.10+
- Click for CLI framework
- Subprocess-based git operations (no gitpython dependency for simplicity)
- TOML configuration files
- Shell wrappers for cd integration

## Non-Goals (Future Considerations)

- `wt clone` - Clone with pre-configuration
- `wt sync` - Pull/rebase all worktrees
- `wt exec` - Run command across all worktrees
- Worktree templates
- Agent tracking
- Locking mechanism
