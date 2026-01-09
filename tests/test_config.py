"""Tests for settings and profile configuration."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile

from gtkmud.config.settings import (
    Settings, DisplaySettings, SoundSettings,
    AccessibilitySettings, NetworkSettings,
)
from gtkmud.config.profiles import MudProfile, ProfileManager


class TestDisplaySettings:
    """Test DisplaySettings dataclass."""

    def test_defaults(self):
        """DisplaySettings should have correct defaults."""
        settings = DisplaySettings()
        assert settings.font_family == "Monospace"
        assert settings.font_size == 12
        assert settings.max_lines == 10000
        assert settings.echo_commands is True

    def test_custom_values(self):
        """DisplaySettings should accept custom values."""
        settings = DisplaySettings(
            font_family="Ubuntu Mono",
            font_size=14,
            max_lines=5000,
            echo_commands=False,
        )
        assert settings.font_family == "Ubuntu Mono"
        assert settings.font_size == 14
        assert settings.max_lines == 5000
        assert settings.echo_commands is False


class TestSoundSettings:
    """Test SoundSettings dataclass."""

    def test_defaults(self):
        """SoundSettings should have correct defaults."""
        settings = SoundSettings()
        assert settings.enabled is True
        assert settings.master_volume == 100
        assert settings.sound_volume == 100
        assert settings.music_volume == 80
        assert settings.ambience_volume == 60

    def test_custom_values(self):
        """SoundSettings should accept custom values."""
        settings = SoundSettings(
            enabled=False,
            master_volume=80,
            sound_volume=70,
            music_volume=50,
            ambience_volume=40,
        )
        assert settings.enabled is False
        assert settings.master_volume == 80
        assert settings.sound_volume == 70
        assert settings.music_volume == 50
        assert settings.ambience_volume == 40


class TestAccessibilitySettings:
    """Test AccessibilitySettings dataclass."""

    def test_defaults(self):
        """AccessibilitySettings should have correct defaults."""
        settings = AccessibilitySettings()
        assert settings.announce_incoming is True
        assert settings.announce_interval_ms == 100

    def test_custom_values(self):
        """AccessibilitySettings should accept custom values."""
        settings = AccessibilitySettings(
            announce_incoming=False,
            announce_interval_ms=200,
        )
        assert settings.announce_incoming is False
        assert settings.announce_interval_ms == 200


class TestNetworkSettings:
    """Test NetworkSettings dataclass."""

    def test_defaults(self):
        """NetworkSettings should have correct defaults."""
        settings = NetworkSettings()
        assert settings.reconnect_on_disconnect is False
        assert settings.reconnect_delay_seconds == 5
        assert settings.encoding == "utf-8"

    def test_custom_values(self):
        """NetworkSettings should accept custom values."""
        settings = NetworkSettings(
            reconnect_on_disconnect=True,
            reconnect_delay_seconds=10,
            encoding="latin-1",
        )
        assert settings.reconnect_on_disconnect is True
        assert settings.reconnect_delay_seconds == 10
        assert settings.encoding == "latin-1"


class TestSettings:
    """Test Settings dataclass."""

    def test_defaults(self):
        """Settings should have default sub-settings."""
        settings = Settings()
        assert isinstance(settings.display, DisplaySettings)
        assert isinstance(settings.sound, SoundSettings)
        assert isinstance(settings.accessibility, AccessibilitySettings)
        assert isinstance(settings.network, NetworkSettings)
        assert settings.last_profile_id == ""

    def test_load_missing_file(self):
        """Loading from missing file should return defaults."""
        with patch('gtkmud.config.settings.get_settings_file') as mock_file:
            mock_path = MagicMock()
            mock_path.exists.return_value = False
            mock_file.return_value = mock_path

            with patch('gtkmud.config.settings.ensure_directories'):
                settings = Settings.load()

            assert isinstance(settings, Settings)
            assert settings.display.font_size == 12  # default

    def test_save_and_load(self):
        """Settings should round-trip through save/load."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.toml"

            with patch('gtkmud.config.settings.get_settings_file', return_value=settings_file):
                with patch('gtkmud.config.settings.ensure_directories'):
                    # Create custom settings
                    settings = Settings()
                    settings.display.font_size = 16
                    settings.sound.master_volume = 75
                    settings.last_profile_id = "test-profile"

                    # Save
                    settings.save()

                    # Load
                    loaded = Settings.load()

                    assert loaded.display.font_size == 16
                    assert loaded.sound.master_volume == 75
                    assert loaded.last_profile_id == "test-profile"


class TestMudProfile:
    """Test MudProfile dataclass."""

    def test_defaults(self):
        """MudProfile should have correct defaults."""
        profile = MudProfile()
        assert profile.name == ""
        assert profile.host == ""
        assert profile.port == 23
        assert profile.auto_connect is False
        assert profile.use_ssl is False
        assert profile.username == ""
        assert profile.script_file == ""
        assert profile.encoding == "utf-8"

    def test_auto_id_generation(self):
        """MudProfile should auto-generate ID if not provided."""
        profile = MudProfile(name="Test", host="example.com")
        assert profile.id != ""
        assert len(profile.id) == 36  # UUID format

    def test_provided_id_preserved(self):
        """MudProfile should preserve provided ID."""
        profile = MudProfile(id="custom-id", name="Test", host="example.com")
        assert profile.id == "custom-id"

    def test_custom_values(self):
        """MudProfile should accept custom values."""
        profile = MudProfile(
            name="Test MUD",
            host="mud.example.com",
            port=4000,
            auto_connect=True,
            use_ssl=True,
            username="player",
            script_file="/path/to/script.mud",
            encoding="latin-1",
        )
        assert profile.name == "Test MUD"
        assert profile.host == "mud.example.com"
        assert profile.port == 4000
        assert profile.auto_connect is True
        assert profile.use_ssl is True
        assert profile.username == "player"
        assert profile.script_file == "/path/to/script.mud"
        assert profile.encoding == "latin-1"


class TestProfileManager:
    """Test ProfileManager class."""

    def test_empty_manager(self):
        """ProfileManager with no profiles should be empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            profiles_file = Path(tmpdir) / "profiles.toml"

            with patch('gtkmud.config.profiles.get_profiles_file', return_value=profiles_file):
                with patch('gtkmud.config.profiles.ensure_directories'):
                    manager = ProfileManager()
                    assert manager.list_profiles() == []

    def test_create_profile(self):
        """ProfileManager should create and save profiles."""
        with tempfile.TemporaryDirectory() as tmpdir:
            profiles_file = Path(tmpdir) / "profiles.toml"

            with patch('gtkmud.config.profiles.get_profiles_file', return_value=profiles_file):
                with patch('gtkmud.config.profiles.ensure_directories'):
                    manager = ProfileManager()
                    profile = manager.create_profile(
                        name="Test MUD",
                        host="mud.example.com",
                        port=4000,
                    )

                    assert profile.name == "Test MUD"
                    assert profile.host == "mud.example.com"
                    assert profile.port == 4000
                    assert profile.id != ""

                    # Should be in the list
                    profiles = manager.list_profiles()
                    assert len(profiles) == 1
                    assert profiles[0].name == "Test MUD"

    def test_get_profile_by_id(self):
        """ProfileManager should get profile by ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            profiles_file = Path(tmpdir) / "profiles.toml"

            with patch('gtkmud.config.profiles.get_profiles_file', return_value=profiles_file):
                with patch('gtkmud.config.profiles.ensure_directories'):
                    manager = ProfileManager()
                    profile = manager.create_profile(
                        name="Test",
                        host="example.com",
                    )

                    retrieved = manager.get_profile(profile.id)
                    assert retrieved is not None
                    assert retrieved.name == "Test"

    def test_get_profile_by_name(self):
        """ProfileManager should get profile by name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            profiles_file = Path(tmpdir) / "profiles.toml"

            with patch('gtkmud.config.profiles.get_profiles_file', return_value=profiles_file):
                with patch('gtkmud.config.profiles.ensure_directories'):
                    manager = ProfileManager()
                    manager.create_profile(name="Test MUD", host="example.com")

                    # Case insensitive
                    profile = manager.get_profile_by_name("test mud")
                    assert profile is not None
                    assert profile.name == "Test MUD"

    def test_get_nonexistent_profile(self):
        """Getting nonexistent profile should return None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            profiles_file = Path(tmpdir) / "profiles.toml"

            with patch('gtkmud.config.profiles.get_profiles_file', return_value=profiles_file):
                with patch('gtkmud.config.profiles.ensure_directories'):
                    manager = ProfileManager()
                    assert manager.get_profile("nonexistent") is None
                    assert manager.get_profile_by_name("nonexistent") is None

    def test_delete_profile(self):
        """ProfileManager should delete profiles."""
        with tempfile.TemporaryDirectory() as tmpdir:
            profiles_file = Path(tmpdir) / "profiles.toml"

            with patch('gtkmud.config.profiles.get_profiles_file', return_value=profiles_file):
                with patch('gtkmud.config.profiles.ensure_directories'):
                    manager = ProfileManager()
                    profile = manager.create_profile(name="Test", host="example.com")

                    assert manager.delete_profile(profile.id) is True
                    assert manager.get_profile(profile.id) is None
                    assert len(manager.list_profiles()) == 0

    def test_delete_nonexistent_profile(self):
        """Deleting nonexistent profile should return False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            profiles_file = Path(tmpdir) / "profiles.toml"

            with patch('gtkmud.config.profiles.get_profiles_file', return_value=profiles_file):
                with patch('gtkmud.config.profiles.ensure_directories'):
                    manager = ProfileManager()
                    assert manager.delete_profile("nonexistent") is False

    def test_save_profile_update(self):
        """ProfileManager should update existing profile."""
        with tempfile.TemporaryDirectory() as tmpdir:
            profiles_file = Path(tmpdir) / "profiles.toml"

            with patch('gtkmud.config.profiles.get_profiles_file', return_value=profiles_file):
                with patch('gtkmud.config.profiles.ensure_directories'):
                    manager = ProfileManager()
                    profile = manager.create_profile(name="Test", host="example.com")

                    # Update
                    profile.port = 5000
                    manager.save_profile(profile)

                    # Verify
                    retrieved = manager.get_profile(profile.id)
                    assert retrieved.port == 5000

    def test_profiles_sorted_by_name(self):
        """list_profiles should return profiles sorted by name."""
        with tempfile.TemporaryDirectory() as tmpdir:
            profiles_file = Path(tmpdir) / "profiles.toml"

            with patch('gtkmud.config.profiles.get_profiles_file', return_value=profiles_file):
                with patch('gtkmud.config.profiles.ensure_directories'):
                    manager = ProfileManager()
                    manager.create_profile(name="Zebra MUD", host="z.com")
                    manager.create_profile(name="Alpha MUD", host="a.com")
                    manager.create_profile(name="Beta MUD", host="b.com")

                    profiles = manager.list_profiles()
                    names = [p.name for p in profiles]
                    assert names == ["Alpha MUD", "Beta MUD", "Zebra MUD"]

    def test_persistence(self):
        """Profiles should persist across manager instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            profiles_file = Path(tmpdir) / "profiles.toml"

            with patch('gtkmud.config.profiles.get_profiles_file', return_value=profiles_file):
                with patch('gtkmud.config.profiles.ensure_directories'):
                    # Create profile
                    manager1 = ProfileManager()
                    profile = manager1.create_profile(
                        name="Persistent MUD",
                        host="persistent.com",
                        port=4000,
                    )
                    profile_id = profile.id

                    # New manager instance should load it
                    manager2 = ProfileManager()
                    loaded = manager2.get_profile(profile_id)
                    assert loaded is not None
                    assert loaded.name == "Persistent MUD"
                    assert loaded.host == "persistent.com"
                    assert loaded.port == 4000


class TestSettingsFields:
    """Test Settings with various field combinations."""

    def test_partial_toml_load(self):
        """Settings should handle partial TOML data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.toml"

            # Write partial settings (only display)
            settings_file.write_text("""
[display]
font_size = 18

[sound]
enabled = false
""")

            with patch('gtkmud.config.settings.get_settings_file', return_value=settings_file):
                with patch('gtkmud.config.settings.ensure_directories'):
                    settings = Settings.load()

                    # Custom values loaded
                    assert settings.display.font_size == 18
                    assert settings.sound.enabled is False

                    # Defaults for unspecified
                    assert settings.display.font_family == "Monospace"
                    assert settings.sound.master_volume == 100
                    assert settings.accessibility.announce_incoming is True

    def test_unknown_fields_ignored(self):
        """Settings should ignore unknown fields in TOML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_file = Path(tmpdir) / "settings.toml"

            # Write settings with unknown field
            settings_file.write_text("""
[display]
font_size = 14
unknown_field = "ignored"
""")

            with patch('gtkmud.config.settings.get_settings_file', return_value=settings_file):
                with patch('gtkmud.config.settings.ensure_directories'):
                    settings = Settings.load()
                    assert settings.display.font_size == 14
                    # Should not crash on unknown field
