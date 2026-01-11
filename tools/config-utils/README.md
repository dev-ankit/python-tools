# config-utils

A CLI tool for capturing environment variables and Django settings in YAML format.

## Features

- **capture-env**: Capture all environment variables and export them to YAML
- **capture-django-settings**: Capture Django project settings and export them to YAML

## Installation

### Using uv tool install (Recommended)

Install the tool globally using `uv`:

```bash
uv tool install .
```

Or install from a remote location:

```bash
uv tool install config-utils
```

This will install the `config-utils` executable in your PATH.

### Using uvx

Run the tool directly without installation:

```bash
uvx --from . config-utils capture-env
```

### Using pip

Install from the local directory:

```bash
pip install .
```

Or install in editable mode for development:

```bash
pip install -e .
```


## Usage

### Capture Environment Variables

Capture all environment variables to a YAML file:

```bash
config-utils capture-env
```

This will create `env_config.yaml` with all your environment variables.

#### Options

- `-o, --output PATH`: Specify output file path (default: `env_config.yaml`)
- `-f, --format`: Output format, yaml or yml (default: `yaml`)

#### Examples

```bash
# Capture to custom file
config-utils capture-env -o my_env.yaml

# Capture with yml extension
config-utils capture-env -o config.yml -f yml
```

### Capture Django Settings

Capture Django project settings to a YAML file using `python manage.py shell`:

```bash
# Run from your Django project directory
cd /path/to/your/django/project
config-utils capture-django-settings
```

This will create `django_settings.yaml` with all Django settings.

#### Options

- `-o, --output PATH`: Specify output file path (default: `django_settings.yaml`)
- `-f, --format`: Output format, yaml or yml (default: `yaml`)
- `-m, --manage-py PATH`: Path to manage.py (default: `manage.py`)
- `-s, --settings`: Django settings module (e.g., `myproject.settings`)

#### Examples

```bash
# From Django project root directory
config-utils capture-django-settings

# Specifying settings module via command line
config-utils capture-django-settings -s myproject.settings

# Custom output file
config-utils capture-django-settings -o my_django_config.yaml

# Specify manage.py path if not in current directory
config-utils capture-django-settings -m /path/to/manage.py

# Using DJANGO_SETTINGS_MODULE environment variable
export DJANGO_SETTINGS_MODULE=myproject.settings
config-utils capture-django-settings
```

**Note**: This command must be run from your Django project directory or you must specify the path to `manage.py` using the `--manage-py` option.

### Using with uvx

You can run the tool directly without installation:

```bash
# Capture environment variables
uvx --from . config-utils capture-env

# With options
uvx --from . config-utils capture-env -o custom.yaml

# Django settings (from Django project directory)
cd /path/to/django/project
uvx --from /path/to/config-utils config-utils capture-django-settings

# Or specify manage.py path
uvx --from /path/to/config-utils config-utils capture-django-settings -m /path/to/manage.py
```

## Requirements

- Python >= 3.8
- click >= 8.0.0
- pyyaml >= 6.0

**For Django settings capture**: The command uses `python manage.py shell`, so Django must be installed in your Django project's environment. The config-utils tool itself does not need Django as a dependency.

## Development

### Setup

```bash
# Clone or navigate to the project directory
cd config-utils

# Install in editable mode with development dependencies
pip install -e .
```

### Project Structure

```
config-utils/
├── cli.py
├── config_utils/
├── pyproject.toml
└── README.md
```

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
