# Development Notes for `wt`

## 2026-01-17: Project Setup

### Design Decisions

1. **Git Operations**: Using subprocess calls to git CLI instead of gitpython
   - Rationale: Simpler, no external dependencies, guaranteed compatibility
   - All git commands wrapped in git.py module for consistency

2. **Configuration**: Using TOML format
   - Local config: `.wt.toml` in repo root
   - Global config: `~/.wt.toml` in home directory
   - Local overrides global

3. **Shell Integration**: Using wrapper function approach
   - CLI outputs target path on success for `wt switch`
   - Shell wrapper intercepts and performs `cd`
   - Different syntax for bash/zsh vs fish

4. **Exit Codes**: Standardized across all commands
   - 0: Success
   - 1: General error
   - 2: Invalid arguments
   - 3: Git error
   - 4: Worktree not found
   - 5: User cancelled

### Project Structure

```
wt-worktree/
├── pyproject.toml
├── PRD.md
├── notes.md
├── README.md
├── wt/
│   ├── __init__.py
│   ├── __main__.py      # Entry point
│   ├── cli.py           # Click commands
│   ├── config.py        # Configuration management
│   ├── git.py           # Git operations
│   ├── worktree.py      # Worktree operations
│   ├── shell.py         # Shell integration
│   └── prompts.py       # User prompts
└── tests/
    ├── __init__.py
    ├── test_config.py
    ├── test_git.py
    ├── test_worktree.py
    └── test_cli.py
```

### Implementation Order

1. Core modules (git.py, config.py, worktree.py)
2. Basic CLI commands (init, switch, list)
3. Management commands (diff, delete, status)
4. Advanced features (run, clean, config)
5. Shell integration
6. Comprehensive testing

### Testing Strategy

- Use real git repositories for testing (not mocks)
- Create temporary test repos in /tmp
- Test both success and error cases
- Test user prompts with environment variable overrides
- Test shell integration with subprocess

### Challenges and Solutions

1. **Git Commit Signing in Tests**
   - Problem: Tests were failing because git was configured to sign commits, but signing was failing
   - Solution: Added `git config commit.gpgsign false` in test fixtures
   - Lesson: Always disable GPG signing in test environments

2. **Test Directory Cleanup Issues**
   - Problem: Tests were failing with `FileNotFoundError` when calling `os.getcwd()` because previous tests had deleted the current directory
   - Solution: Wrapped `os.getcwd()` in try-except and fallback to `/tmp`
   - Lesson: Be careful with directory changes in tests, always handle cleanup gracefully

3. **Remote References in Tests**
   - Problem: Tests were failing because default_base was set to `origin/main` but test repos don't have remotes
   - Solution: Set `default_base` to `main` in test fixtures
   - Lesson: Make config values appropriate for test environment

4. **Uncommitted Files in Status Tests**
   - Problem: Test for clean worktree was failing because `.wt.toml` was uncommitted
   - Solution: Commit the config file in the manager fixture
   - Lesson: Ensure test setup leaves repository in expected state

5. **TOML Library Compatibility**
   - Problem: Need to support Python 3.10 which doesn't have built-in tomllib
   - Solution: Added conditional import with fallback to tomli package
   - Lesson: Always consider Python version compatibility

6. **Config Not Found in Secondary Worktrees**
   - Problem: When running wt commands from a secondary worktree, it would ask to run `wt init` again because it couldn't find `.wt.toml`
   - Initial Solution: Added `get_main_worktree_root()` function to find main worktree
   - Better Solution: Simplified to use global config in `~/.wt.toml` (or `$WT_CONFIG/.wt.toml`)
   - Rationale: Simpler design, no need to find main worktree, works the same everywhere
   - Changes:
     - Config now stored in one place (home directory by default)
     - Removed local repo config concept
     - `wt init` is now optional (just sets custom defaults)
     - No need to run `wt init` per repository
   - Lesson: Sometimes the simplest solution is the best - global config is easier than per-repo config for this use case

### Test Results

- **Total Tests**: 58
- **Passed**: 58
- **Coverage**: 63%
- **Key Coverage Areas**:
  - git.py: 86% (core git operations well tested, including worktree detection)
  - config.py: 75% (configuration management tested)
  - worktree.py: 62% (worktree operations tested)
  - cli.py: 54% (CLI commands tested including secondary worktree usage)

7. **Missing Special Symbol Support in `wt run`**
   - Problem: The `wt run` command didn't support the `^` symbol for the default worktree, while `wt switch ^` did
   - Error: Running `wt run ^ "git status"` resulted in "Error: Worktree '^' not found"
   - Solution: Added special handling for the `^` symbol in the `run` command (cli.py:373-380) to resolve it to the default worktree name before looking up the worktree
   - Implementation: Added check `if name == "^":` to get the default worktree using `ctx.manager.get_default_worktree()` and then use its name
   - Tests: Added three new tests in test_cli.py:
     - `test_run_command`: Tests running a command in a normal worktree
     - `test_run_command_with_default_symbol`: Tests running a command using `^` symbol
     - `test_run_command_nonexistent_worktree`: Tests error handling for non-existent worktrees
   - Lesson: Always ensure consistency across commands - if a special symbol works in one command, users will expect it to work in related commands too

### Future Improvements

1. **Increase CLI Test Coverage**: Add more edge case tests for CLI commands
2. **Integration Tests**: Add end-to-end tests with real workflows
3. **Shell Integration Tests**: Test actual shell wrapper execution
4. **Error Message Tests**: Verify all error messages are clear and actionable
5. **Performance**: Optimize git operations for large repositories
