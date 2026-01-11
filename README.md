# Python Tools

A collection of small, independent Python utilities. Each tool is self-contained with its own dependencies and can be installed/run independently.

## Tools

| Tool | Description |
|------|-------------|
| [locust-compare](tools/locust-compare/) | Compare performance metrics between two Locust runs |
| [config-utils](tools/config-utils/) | CLI tool for capturing environment variables and Django settings |

## Installation

Option 1: uv tool install

Each tool can be installed independently using `uvx` directly from GitHub:

For example:
```bash
# Install locust-compare
uv tool install 'git+https://github.com/dev-ankit/python-tools.git#subdirectory=tools/locust-compare'

# Install config-utils
uv tool install 'git+https://github.com/dev-ankit/python-tools.git#subdirectory=tools/config-utils'
```

After installation, you can run from anywhere:
```bash
locust-compare <base_dir> <current_dir>
config-utils capture-env
```

To update to the latest from GitHub:

```bash
uv tool upgrade locust-compare
uv tool upgrade config-utils

# Or force reinstall:
uv tool install --force 'git+https://github.com/dev-ankit/python-tools.git#subdirectory=tools/locust-compare'
uv tool install --force 'git+https://github.com/dev-ankit/python-tools.git#subdirectory=tools/config-utils'

# To see installed tools:
uv tool list
```

Option 2: Run directly

```bash
uvx --from 'git+https://github.com/dev-ankit/python-tools.git#subdirectory=tools/<tool-name>' <tool-name> [args]
```

For example:

```bash
# Run locust-compare
uvx --from 'git+https://github.com/dev-ankit/python-tools.git#subdirectory=tools/locust-compare' locust-compare <base_dir> <current_dir>

# Run config-utils
uvx --from 'git+https://github.com/dev-ankit/python-tools.git#subdirectory=tools/config-utils' config-utils capture-env
```

Option 3: Clone and run locally:

```bash
git clone https://github.com/dev-ankit/python-tools.git
cd python-tools/tools/<tool-name>
uvx --from . <tool-name> [args]
```

## Repository Structure

```
python-tools/
├── README.md      
├── LICENSE             # MIT License (shared)
├── .github/
│   └── workflows/
└── tools/
    ├── locust-compare/ # Locust performance comparison tool
    │   ├── compare_runs.py
    │   ├── pyproject.toml
    │   ├── README.md
    │   └── tests/
    └── config-utils/ # CLI tool for capturing environment variables and Django settings
        ├── cli.py
        ├── pyproject.toml
        └── README.md
```

## Adding a New Tool

1. Create a new directory under `tools/`: `tools/your-tool-name/`
2. Add your tool's source files and a `pyproject.toml`
3. Add a `README.md` with usage instructions
4. Update the CI workflow if needed
5. Add an entry to the Tools table in this README

## License

MIT License - see [LICENSE](LICENSE) for details.
