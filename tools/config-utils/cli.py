"""CLI commands for config-utils."""

import os
import sys
import yaml
import subprocess
import json
from pathlib import Path
import click


@click.group()
@click.version_option()
def main():
    """config-utils: Capture environment variables and Django settings."""
    pass


@main.command()
@click.option(
    '--output',
    '-o',
    default='env_config.yaml',
    help='Output file path (default: env_config.yaml)',
    type=click.Path(),
)
@click.option(
    '--format',
    '-f',
    type=click.Choice(['yaml', 'yml'], case_sensitive=False),
    default='yaml',
    help='Output format (default: yaml)',
)
def capture_env(output, format):
    """Capture all environment variables and store them in YAML format."""
    try:
        # Get all environment variables
        env_vars = dict(os.environ)

        # Ensure output path is Path object
        output_path = Path(output)

        # Write to YAML file
        with open(output_path, 'w') as f:
            yaml.dump(env_vars, f, default_flow_style=False, sort_keys=True)

        click.echo(f"✓ Captured {len(env_vars)} environment variables to {output_path}")

    except Exception as e:
        click.echo(f"✗ Error: {str(e)}", err=True)
        sys.exit(1)


@main.command()
@click.option(
    '--output',
    '-o',
    default='django_settings.yaml',
    help='Output file path (default: django_settings.yaml)',
    type=click.Path(),
)
@click.option(
    '--format',
    '-f',
    type=click.Choice(['yaml', 'yml'], case_sensitive=False),
    default='yaml',
    help='Output format (default: yaml)',
)
@click.option(
    '--manage-py',
    '-m',
    default='manage.py',
    help='Path to manage.py (default: manage.py)',
    type=click.Path(exists=True),
)
@click.option(
    '--settings',
    '-s',
    help='Django settings module (e.g., myproject.settings)',
    envvar='DJANGO_SETTINGS_MODULE',
)
def capture_django_settings(output, format, manage_py, settings):
    """Capture Django settings and store them in YAML format.

    Uses 'python manage.py shell' to access Django settings.
    Requires manage.py to be present in the current directory or specify path with --manage-py.
    """
    try:
        # Check if manage.py exists
        manage_path = Path(manage_py)
        if not manage_path.exists():
            click.echo(
                f"✗ Error: manage.py not found at {manage_path}. "
                "Run this command from your Django project root or use --manage-py to specify the path.",
                err=True
            )
            sys.exit(1)

        # Python script to run in Django shell
        django_script = """
import json
from django.conf import settings

settings_dict = {}
for setting in dir(settings):
    if setting.isupper():
        try:
            value = getattr(settings, setting)
            # Convert non-serializable types to strings
            if not isinstance(value, (str, int, float, bool, list, dict, type(None))):
                value = str(value)
            settings_dict[setting] = value
        except Exception as e:
            settings_dict[setting] = f"<Error retrieving value: {str(e)}>"

print(json.dumps(settings_dict))
"""

        # Prepare environment variables
        env = os.environ.copy()
        if settings:
            env['DJANGO_SETTINGS_MODULE'] = settings

        # Run manage.py shell with the script
        result = subprocess.run(
            ['python', str(manage_path), 'shell'],
            input=django_script,
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )

        if result.returncode != 0:
            click.echo(f"✗ Error running Django shell:", err=True)
            click.echo(result.stderr, err=True)
            sys.exit(1)

        # Parse JSON output
        try:
            settings_dict = json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            click.echo(f"✗ Error: Could not parse Django settings output", err=True)
            click.echo(f"Output: {result.stdout}", err=True)
            sys.exit(1)

        # Ensure output path is Path object
        output_path = Path(output)

        # Write to YAML file
        with open(output_path, 'w') as f:
            yaml.dump(settings_dict, f, default_flow_style=False, sort_keys=True)

        click.echo(f"✓ Captured {len(settings_dict)} Django settings to {output_path}")

    except subprocess.TimeoutExpired:
        click.echo("✗ Error: Django shell command timed out", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"✗ Error: {str(e)}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
