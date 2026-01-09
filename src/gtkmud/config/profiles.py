"""MUD profile management."""

import logging
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

try:
    import tomllib
except ImportError:
    import tomli as tomllib

import tomli_w

from gtkmud.config.paths import get_profiles_file, ensure_directories

logger = logging.getLogger(__name__)


@dataclass
class MudProfile:
    """A MUD server profile."""
    id: str = ""
    name: str = ""
    host: str = ""
    port: int = 23
    auto_connect: bool = False
    use_ssl: bool = False
    username: str = ""
    script_file: str = ""
    encoding: str = "utf-8"

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())


class ProfileManager:
    """Manages MUD profiles."""

    def __init__(self):
        self._profiles: dict[str, MudProfile] = {}
        self._load()

    def _load(self) -> None:
        """Load profiles from file."""
        ensure_directories()
        profiles_file = get_profiles_file()

        if not profiles_file.exists():
            logger.info("No profiles file found")
            return

        try:
            with open(profiles_file, "rb") as f:
                data = tomllib.load(f)

            profiles_list = data.get("profiles", [])
            for profile_data in profiles_list:
                profile = MudProfile(**profile_data)
                self._profiles[profile.id] = profile

            logger.info(f"Loaded {len(self._profiles)} profiles")

        except Exception as e:
            logger.error(f"Error loading profiles: {e}")

    def _save(self) -> None:
        """Save profiles to file."""
        ensure_directories()
        profiles_file = get_profiles_file()

        data = {
            "profiles": [asdict(p) for p in self._profiles.values()]
        }

        try:
            with open(profiles_file, "wb") as f:
                tomli_w.dump(data, f)
            logger.info(f"Saved {len(self._profiles)} profiles")
        except Exception as e:
            logger.error(f"Error saving profiles: {e}")

    def list_profiles(self) -> list[MudProfile]:
        """Get all profiles sorted by name."""
        return sorted(self._profiles.values(), key=lambda p: p.name.lower())

    def get_profile(self, profile_id: str) -> Optional[MudProfile]:
        """Get a profile by ID."""
        return self._profiles.get(profile_id)

    def get_profile_by_name(self, name: str) -> Optional[MudProfile]:
        """Get a profile by name."""
        for profile in self._profiles.values():
            if profile.name.lower() == name.lower():
                return profile
        return None

    def save_profile(self, profile: MudProfile) -> None:
        """Save or update a profile."""
        if not profile.id:
            profile.id = str(uuid.uuid4())
        self._profiles[profile.id] = profile
        self._save()

    def delete_profile(self, profile_id: str) -> bool:
        """Delete a profile by ID."""
        if profile_id in self._profiles:
            del self._profiles[profile_id]
            self._save()
            return True
        return False

    def create_profile(
        self,
        name: str,
        host: str,
        port: int = 23,
        auto_connect: bool = False,
        script_file: str = "",
        use_ssl: bool = False,
    ) -> MudProfile:
        """Create and save a new profile."""
        profile = MudProfile(
            name=name,
            host=host,
            port=port,
            auto_connect=auto_connect,
            script_file=script_file,
            use_ssl=use_ssl,
        )
        self.save_profile(profile)
        return profile


# Global profile manager instance
_profile_manager: Optional[ProfileManager] = None


def get_profile_manager() -> ProfileManager:
    """Get the global profile manager instance."""
    global _profile_manager
    if _profile_manager is None:
        _profile_manager = ProfileManager()
    return _profile_manager
