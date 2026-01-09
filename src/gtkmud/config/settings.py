"""User settings management."""

import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

try:
    import tomllib
except ImportError:
    import tomli as tomllib

import tomli_w

from gtkmud.config.paths import get_settings_file, ensure_directories

logger = logging.getLogger(__name__)


@dataclass
class DisplaySettings:
    """Display-related settings."""
    font_family: str = "Monospace"
    font_size: int = 12
    max_lines: int = 10000
    echo_commands: bool = True  # Show typed commands in output


@dataclass
class SoundSettings:
    """Sound-related settings."""
    enabled: bool = True
    master_volume: int = 100
    sound_volume: int = 100
    music_volume: int = 80
    ambience_volume: int = 60


@dataclass
class AccessibilitySettings:
    """Accessibility-related settings."""
    announce_incoming: bool = True
    announce_interval_ms: int = 100


@dataclass
class NetworkSettings:
    """Network-related settings."""
    reconnect_on_disconnect: bool = False
    reconnect_delay_seconds: int = 5
    encoding: str = "utf-8"


@dataclass
class Settings:
    """All user settings."""
    display: DisplaySettings = field(default_factory=DisplaySettings)
    sound: SoundSettings = field(default_factory=SoundSettings)
    accessibility: AccessibilitySettings = field(default_factory=AccessibilitySettings)
    network: NetworkSettings = field(default_factory=NetworkSettings)
    last_profile_id: str = ""

    @classmethod
    def load(cls) -> "Settings":
        """Load settings from file."""
        ensure_directories()
        settings_file = get_settings_file()

        if not settings_file.exists():
            logger.info("No settings file found, using defaults")
            return cls()

        try:
            with open(settings_file, "rb") as f:
                data = tomllib.load(f)

            settings = cls()

            if "display" in data:
                for key, value in data["display"].items():
                    if hasattr(settings.display, key):
                        setattr(settings.display, key, value)

            if "sound" in data:
                for key, value in data["sound"].items():
                    if hasattr(settings.sound, key):
                        setattr(settings.sound, key, value)

            if "accessibility" in data:
                for key, value in data["accessibility"].items():
                    if hasattr(settings.accessibility, key):
                        setattr(settings.accessibility, key, value)

            if "network" in data:
                for key, value in data["network"].items():
                    if hasattr(settings.network, key):
                        setattr(settings.network, key, value)

            if "last_profile_id" in data:
                settings.last_profile_id = data["last_profile_id"]

            logger.info(f"Loaded settings from {settings_file}")
            return settings

        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            return cls()

    def save(self) -> None:
        """Save settings to file."""
        ensure_directories()
        settings_file = get_settings_file()

        data = {
            "display": asdict(self.display),
            "sound": asdict(self.sound),
            "accessibility": asdict(self.accessibility),
            "network": asdict(self.network),
            "last_profile_id": self.last_profile_id,
        }

        try:
            with open(settings_file, "wb") as f:
                tomli_w.dump(data, f)
            logger.info(f"Saved settings to {settings_file}")
        except Exception as e:
            logger.error(f"Error saving settings: {e}")


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings.load()
    return _settings


def save_settings() -> None:
    """Save the global settings."""
    if _settings is not None:
        _settings.save()
