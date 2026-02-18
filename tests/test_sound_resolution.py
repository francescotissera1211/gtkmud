"""Tests for sound file resolution: case-insensitive and numbered variant selection."""

import pytest
from pathlib import Path
from unittest.mock import patch
import tempfile

from gtkmud.sound.manager import SoundManager


@pytest.fixture
def sound_dir():
    """Create a temp sounds directory with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sounds = Path(tmpdir) / "sounds"
        sounds.mkdir()
        yield sounds


@pytest.fixture
def manager(sound_dir):
    """Create a SoundManager with a temp sounds directory."""
    cache_dir = sound_dir.parent / "cache"
    cache_dir.mkdir()
    return SoundManager(cache_dir=cache_dir, sounds_dir=sound_dir)


class TestExactMatch:
    """Exact filename resolution (existing behaviour)."""

    def test_exact_match(self, sound_dir, manager):
        path = sound_dir / "beep.ogg"
        path.touch()
        assert manager._find_sound_file("beep.ogg") == path

    def test_exact_match_nested(self, sound_dir, manager):
        (sound_dir / "miriani" / "misc").mkdir(parents=True)
        path = sound_dir / "miriani" / "misc" / "cash.ogg"
        path.touch()
        assert manager._find_sound_file("miriani/misc/cash.ogg") == path

    def test_extension_fallback(self, sound_dir, manager):
        path = sound_dir / "beep.ogg"
        path.touch()
        assert manager._find_sound_file("beep") == path

    def test_not_found(self, sound_dir, manager):
        assert manager._find_sound_file("nonexistent.ogg") is None


class TestCaseInsensitive:
    """Case-insensitive file resolution."""

    def test_wrong_case_filename(self, sound_dir, manager):
        (sound_dir / "misc").mkdir()
        path = sound_dir / "misc" / "doorClosed.ogg"
        path.touch()
        result = manager._find_sound_file("misc/doorclosed.ogg")
        assert result == path

    def test_wrong_case_directory(self, sound_dir, manager):
        (sound_dir / "Miriani" / "Music").mkdir(parents=True)
        path = sound_dir / "Miriani" / "Music" / "theme1.ogg"
        path.touch()
        result = manager._find_sound_file("miriani/music/theme1.ogg")
        assert result == path

    def test_mixed_case_path(self, sound_dir, manager):
        (sound_dir / "Ship" / "Misc").mkdir(parents=True)
        path = sound_dir / "Ship" / "Misc" / "DockClose.ogg"
        path.touch()
        result = manager._find_sound_file("ship/misc/dockclose.ogg")
        assert result == path

    def test_case_insensitive_not_found(self, sound_dir, manager):
        """Still returns None if no case variation exists."""
        (sound_dir / "misc").mkdir()
        assert manager._find_sound_file("misc/nope.ogg") is None


class TestNumberedVariants:
    """Numbered variant random selection."""

    def test_single_variant(self, sound_dir, manager):
        (sound_dir / "music").mkdir()
        path = sound_dir / "music" / "theme1.ogg"
        path.touch()
        result = manager._find_sound_file("music/theme.ogg")
        assert result == path

    def test_multiple_variants(self, sound_dir, manager):
        (sound_dir / "misc").mkdir()
        paths = []
        for i in range(1, 6):
            p = sound_dir / "misc" / f"creak{i}.ogg"
            p.touch()
            paths.append(p)
        # Run many times to confirm it picks from the set
        results = set()
        for _ in range(50):
            r = manager._find_sound_file("misc/creak.ogg")
            assert r in paths
            results.add(r)
        # With 50 tries and 5 options, we should hit at least 2
        assert len(results) >= 2

    def test_case_insensitive_numbered(self, sound_dir, manager):
        """'command.ogg' should match 'Command1.ogg', 'Command2.ogg' etc."""
        (sound_dir / "misc").mkdir()
        for i in range(1, 4):
            (sound_dir / "misc" / f"Command{i}.ogg").touch()
        result = manager._find_sound_file("misc/command.ogg")
        assert result is not None
        assert result.stem.lower().startswith("command")

    def test_numbered_with_case_insensitive_dirs(self, sound_dir, manager):
        """Directories should also resolve case-insensitively."""
        (sound_dir / "Ship" / "Misc").mkdir(parents=True)
        for i in range(1, 4):
            (sound_dir / "Ship" / "Misc" / f"creak{i}.ogg").touch()
        result = manager._find_sound_file("ship/misc/creak.ogg")
        assert result is not None

    def test_no_false_match(self, sound_dir, manager):
        """'theme.ogg' should NOT match 'othertheme1.ogg'."""
        (sound_dir / "music").mkdir()
        (sound_dir / "music" / "othertheme1.ogg").touch()
        assert manager._find_sound_file("music/theme.ogg") is None

    def test_multi_digit_numbers(self, sound_dir, manager):
        (sound_dir / "music").mkdir()
        for i in [1, 10, 15, 25]:
            (sound_dir / "music" / f"mission{i}.ogg").touch()
        result = manager._find_sound_file("music/mission.ogg")
        assert result is not None
        assert "mission" in result.name.lower()

    def test_different_extensions(self, sound_dir, manager):
        """Should match the requested extension only."""
        (sound_dir / "sfx").mkdir()
        (sound_dir / "sfx" / "boom1.wav").touch()
        (sound_dir / "sfx" / "boom2.wav").touch()
        result = manager._find_sound_file("sfx/boom.wav")
        assert result is not None
        assert result.suffix == ".wav"

    def test_no_numbered_variants(self, sound_dir, manager):
        """Returns None when no numbered variants exist."""
        (sound_dir / "misc").mkdir()
        (sound_dir / "misc" / "unique.ogg").touch()
        assert manager._find_sound_file("misc/other.ogg") is None

    def test_exact_match_preferred_over_numbered(self, sound_dir, manager):
        """If exact file exists, use it instead of numbered variants."""
        (sound_dir / "misc").mkdir()
        exact = sound_dir / "misc" / "beep.ogg"
        exact.touch()
        (sound_dir / "misc" / "beep1.ogg").touch()
        (sound_dir / "misc" / "beep2.ogg").touch()
        # Exact match should always win
        for _ in range(20):
            assert manager._find_sound_file("misc/beep.ogg") == exact
