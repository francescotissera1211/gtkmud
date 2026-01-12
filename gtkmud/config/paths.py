"""XDG-compliant path resolution for GTK MUD."""

import os
from pathlib import Path


def get_config_dir() -> Path:
    """Get the configuration directory.

    Returns XDG_CONFIG_HOME/gtkmud or ~/.config/gtkmud.
    """
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base) / "gtkmud"
    return Path.home() / ".config" / "gtkmud"


def get_data_dir() -> Path:
    """Get the data directory.

    Returns XDG_DATA_HOME/gtkmud or ~/.local/share/gtkmud.
    """
    base = os.environ.get("XDG_DATA_HOME")
    if base:
        return Path(base) / "gtkmud"
    return Path.home() / ".local" / "share" / "gtkmud"


def get_cache_dir() -> Path:
    """Get the cache directory.

    Returns XDG_CACHE_HOME/gtkmud or ~/.cache/gtkmud.
    """
    base = os.environ.get("XDG_CACHE_HOME")
    if base:
        return Path(base) / "gtkmud"
    return Path.home() / ".cache" / "gtkmud"


def get_sounds_dir() -> Path:
    """Get the sounds directory for user sound files."""
    return get_data_dir() / "sounds"


def get_scripts_dir() -> Path:
    """Get the scripts directory for user DSL scripts."""
    return get_data_dir() / "scripts"


def get_profiles_file() -> Path:
    """Get the path to the profiles configuration file."""
    return get_config_dir() / "profiles.toml"


def get_settings_file() -> Path:
    """Get the path to the settings configuration file."""
    return get_config_dir() / "settings.toml"


def ensure_directories():
    """Create all necessary directories if they don't exist."""
    get_config_dir().mkdir(parents=True, exist_ok=True)
    get_data_dir().mkdir(parents=True, exist_ok=True)
    get_cache_dir().mkdir(parents=True, exist_ok=True)
    get_sounds_dir().mkdir(parents=True, exist_ok=True)
    get_scripts_dir().mkdir(parents=True, exist_ok=True)
