"""Configuration management for wt."""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any

# Try tomllib (Python 3.11+), fallback to tomli
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None


class ConfigError(Exception):
    """Raised when configuration operations fail."""
    pass


class Config:
    """Manages wt configuration."""

    DEFAULT_CONFIG = {
        "prefix": "feature",
        "path_pattern": "../{repo}-{name}",
        "default_base": "origin/main",
        "default_worktree": None,  # Auto-detected
    }

    def __init__(self, repo_root: Optional[Path] = None):
        """
        Initialize configuration.

        Args:
            repo_root: Root of the git repository
        """
        self.repo_root = repo_root
        self._config = self.DEFAULT_CONFIG.copy()
        self._load_config()

    def _load_config(self):
        """Load configuration from files."""
        # Load global config first
        global_config = self._get_global_config_path()
        if global_config and global_config.exists():
            self._merge_config(self._read_toml(global_config))

        # Load local config (overrides global)
        if self.repo_root:
            local_config = self.repo_root / ".wt.toml"
            if local_config.exists():
                self._merge_config(self._read_toml(local_config))

    def _read_toml(self, path: Path) -> Dict[str, Any]:
        """Read a TOML file."""
        if tomllib is None:
            raise ConfigError(
                "TOML support not available. "
                "Please install tomli: pip install tomli"
            )

        try:
            with open(path, "rb") as f:
                return tomllib.load(f)
        except Exception as e:
            raise ConfigError(f"Failed to read config from {path}: {e}")

    def _merge_config(self, config: Dict[str, Any]):
        """Merge config dict into current config."""
        self._config.update(config)

    def _get_global_config_path(self) -> Optional[Path]:
        """Get path to global config file."""
        # Check WT_CONFIG environment variable
        if "WT_CONFIG" in os.environ:
            return Path(os.environ["WT_CONFIG"])

        # Default to ~/.wt.toml
        home = Path.home()
        return home / ".wt.toml"

    def get_local_config_path(self) -> Optional[Path]:
        """Get path to local config file."""
        if not self.repo_root:
            return None
        return self.repo_root / ".wt.toml"

    def save_local(self, config: Optional[Dict[str, Any]] = None):
        """
        Save configuration to local .wt.toml file.

        Args:
            config: Config dict to save (uses current config if None)
        """
        if not self.repo_root:
            raise ConfigError("Cannot save local config without repo_root")

        config_path = self.get_local_config_path()
        config_data = config if config is not None else self._config

        # Filter out None values and default_worktree if auto-detected
        filtered = {k: v for k, v in config_data.items()
                   if v is not None and k in self.DEFAULT_CONFIG}

        self._write_toml(config_path, filtered)

    def save_global(self, config: Optional[Dict[str, Any]] = None):
        """
        Save configuration to global ~/.wt.toml file.

        Args:
            config: Config dict to save (uses current config if None)
        """
        config_path = self._get_global_config_path()
        if not config_path:
            raise ConfigError("Cannot determine global config path")

        config_data = config if config is not None else self._config

        # Filter out None values
        filtered = {k: v for k, v in config_data.items()
                   if v is not None and k in self.DEFAULT_CONFIG}

        self._write_toml(config_path, filtered)

    def _write_toml(self, path: Path, data: Dict[str, Any]):
        """Write data to a TOML file."""
        # Simple TOML writer (avoid additional dependencies)
        lines = []
        for key, value in data.items():
            if isinstance(value, str):
                lines.append(f'{key} = "{value}"')
            elif isinstance(value, bool):
                lines.append(f'{key} = {str(value).lower()}')
            elif isinstance(value, (int, float)):
                lines.append(f'{key} = {value}')
            elif value is None:
                lines.append(f'# {key} = null')

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                f.write('\n'.join(lines) + '\n')
        except Exception as e:
            raise ConfigError(f"Failed to write config to {path}: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self._config.get(key, default)

    def set(self, key: str, value: Any):
        """Set a configuration value (in memory only)."""
        if key not in self.DEFAULT_CONFIG:
            raise ConfigError(f"Unknown configuration key: {key}")
        self._config[key] = value

    def get_all(self) -> Dict[str, Any]:
        """Get all configuration values."""
        return self._config.copy()

    def is_initialized(self) -> bool:
        """Check if wt is initialized (local config exists)."""
        if not self.repo_root:
            return False
        return (self.repo_root / ".wt.toml").exists()

    def resolve_path_pattern(self, name: str, branch: str) -> Path:
        """
        Resolve the path pattern for a worktree.

        Args:
            name: Worktree name (suffix)
            branch: Full branch name

        Returns:
            Resolved path
        """
        if not self.repo_root:
            raise ConfigError("Cannot resolve path without repo_root")

        pattern = self.get("path_pattern")
        repo_name = self.repo_root.name

        # Replace variables
        resolved = pattern.replace("{repo}", repo_name)
        resolved = resolved.replace("{name}", name)
        resolved = resolved.replace("{branch}", branch)

        # Resolve relative to repo root
        path = self.repo_root / resolved
        return path.resolve()

    def get_branch_name(self, name: str) -> str:
        """
        Get full branch name from worktree name.

        Args:
            name: Worktree name (suffix)

        Returns:
            Full branch name (prefix/name)
        """
        prefix = self.get("prefix")
        if prefix:
            return f"{prefix}/{name}"
        return name

    def extract_worktree_name(self, branch: str) -> str:
        """
        Extract worktree name from full branch name.

        Args:
            branch: Full branch name

        Returns:
            Worktree name (suffix without prefix)
        """
        prefix = self.get("prefix")
        if prefix and branch.startswith(f"{prefix}/"):
            return branch[len(prefix) + 1:]
        return branch
