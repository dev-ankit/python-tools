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

### Test Results

- **Total Tests**: 57
- **Passed**: 57
- **Coverage**: 63%
- **Key Coverage Areas**:
  - git.py: 83% (core git operations well tested)
  - config.py: 75% (configuration management tested)
  - worktree.py: 62% (worktree operations tested)
  - cli.py: 30% (basic CLI commands tested, some edge cases untested)

### Future Improvements

1. **Increase CLI Test Coverage**: Add more edge case tests for CLI commands
2. **Integration Tests**: Add end-to-end tests with real workflows
3. **Shell Integration Tests**: Test actual shell wrapper execution
4. **Error Message Tests**: Verify all error messages are clear and actionable
5. **Performance**: Optimize git operations for large repositories
