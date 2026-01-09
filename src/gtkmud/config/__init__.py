"""Configuration and profile management."""

from gtkmud.config.paths import (
    get_config_dir, get_data_dir, get_cache_dir,
    get_sounds_dir, get_scripts_dir,
    get_profiles_file, get_settings_file,
    ensure_directories,
)
from gtkmud.config.settings import (
    Settings, get_settings, save_settings,
    DisplaySettings, SoundSettings, AccessibilitySettings, NetworkSettings,
)
from gtkmud.config.profiles import (
    MudProfile, ProfileManager, get_profile_manager,
)

__all__ = [
    # Paths
    "get_config_dir", "get_data_dir", "get_cache_dir",
    "get_sounds_dir", "get_scripts_dir",
    "get_profiles_file", "get_settings_file",
    "ensure_directories",
    # Settings
    "Settings", "get_settings", "save_settings",
    "DisplaySettings", "SoundSettings", "AccessibilitySettings", "NetworkSettings",
    # Profiles
    "MudProfile", "ProfileManager", "get_profile_manager",
]
