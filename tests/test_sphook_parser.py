"""Tests for the SPHook (Cosmic Rage) sound protocol parser."""

import pytest

from gtkmud.parsers.sphook import (
    SPHookParser, SPHookState, BufferAnnouncement,
    COSMIC_RAGE_SOUND_URL,
)


@pytest.fixture
def parser():
    """Create an SPHook parser instance."""
    return SPHookParser()


@pytest.fixture
def ogg_parser():
    """Create an SPHook parser with .ogg extension."""
    return SPHookParser(file_extension=".ogg")


class TestPlayAction:
    """Test $sphook play action parsing."""

    def test_simple_play(self, parser):
        """Parse simple play action."""
        text = "$sphook play:effects/beep:100:1:0:sound1"
        cleaned, triggers, announcements = parser.extract_triggers(text)
        assert len(triggers) == 1
        assert triggers[0].filename == "effects/beep.wav"
        assert triggers[0].loops == 1

    def test_play_volume(self, parser):
        """Parse play with volume."""
        text = "$sphook play:effects/hit:50:1:0:hit1"
        _, triggers, _ = parser.extract_triggers(text)
        assert triggers[0].volume == 50

    def test_play_volume_clamped_high(self, parser):
        """Volume above 100 should be clamped."""
        text = "$sphook play:effects/loud:150:1:0:loud1"
        _, triggers, _ = parser.extract_triggers(text)
        assert triggers[0].volume == 100

    def test_play_volume_clamped_low(self, parser):
        """Volume below 0 should be clamped."""
        text = "$sphook play:effects/quiet:-50:1:0:quiet1"
        _, triggers, _ = parser.extract_triggers(text)
        assert triggers[0].volume == 0

    def test_play_invalid_volume(self, parser):
        """Invalid volume should default to 50."""
        text = "$sphook play:effects/sound:abc:1:0:sound1"
        _, triggers, _ = parser.extract_triggers(text)
        assert triggers[0].volume == 50

    def test_play_url(self, parser):
        """Play should have correct URL."""
        text = "$sphook play:combat/slash:80:1:0:slash1"
        _, triggers, _ = parser.extract_triggers(text)
        expected_url = f"{COSMIC_RAGE_SOUND_URL}wav/"
        assert triggers[0].url == expected_url

    def test_play_ogg_extension(self, ogg_parser):
        """Parser with .ogg extension should use ogg directory."""
        text = "$sphook play:combat/slash:80:1:0:slash1"
        _, triggers, _ = ogg_parser.extract_triggers(text)
        assert triggers[0].filename == "combat/slash.ogg"
        expected_url = f"{COSMIC_RAGE_SOUND_URL}ogg/"
        assert triggers[0].url == expected_url

    def test_play_type_is_sound(self, parser):
        """Regular play should have type 'sound'."""
        text = "$sphook play:effects/click:100:1:0:click1"
        _, triggers, _ = parser.extract_triggers(text)
        assert triggers[0].type == "sound"


class TestLoopAction:
    """Test $sphook loop action parsing."""

    def test_simple_loop(self, parser):
        """Parse simple loop action."""
        text = "$sphook loop:music/background:60:1:0:bgm1"
        _, triggers, _ = parser.extract_triggers(text)
        assert len(triggers) == 1
        assert triggers[0].loops == -1  # Infinite loop

    def test_loop_preserves_other_params(self, parser):
        """Loop should preserve volume and other params."""
        text = "$sphook loop:music/theme:75:1:0:theme1"
        _, triggers, _ = parser.extract_triggers(text)
        assert triggers[0].volume == 75
        assert triggers[0].loops == -1


class TestAmbienceDetection:
    """Test automatic ambience detection from path."""

    def test_ambiance_in_path(self, parser):
        """Path with 'ambiance' should become ambience type."""
        text = "$sphook loop:ambiances/forest:50:1:0:forest1"
        _, triggers, _ = parser.extract_triggers(text)
        assert triggers[0].type == "ambience"

    def test_ambience_in_path(self, parser):
        """Path with 'ambience' should become ambience type."""
        text = "$sphook loop:ambiences/rain:50:1:0:rain1"
        _, triggers, _ = parser.extract_triggers(text)
        assert triggers[0].type == "ambience"

    def test_ambiance_case_insensitive(self, parser):
        """Ambiance detection should be case insensitive."""
        text = "$sphook loop:Ambiances/City:50:1:0:city1"
        _, triggers, _ = parser.extract_triggers(text)
        assert triggers[0].type == "ambience"

    def test_regular_loop_not_ambience(self, parser):
        """Regular loop should not be ambience."""
        text = "$sphook loop:music/battle:80:1:0:battle1"
        _, triggers, _ = parser.extract_triggers(text)
        assert triggers[0].type == "sound"


class TestStopAction:
    """Test $sphook stop action parsing."""

    def test_stop_action(self, parser):
        """Parse stop action."""
        text = "$sphook stop:na:na:na:na:sound1"
        _, triggers, _ = parser.extract_triggers(text)
        assert len(triggers) == 1
        assert triggers[0].is_stop is True

    def test_stop_stores_id(self, parser):
        """Stop action should store the sound ID."""
        text = "$sphook stop:na:na:na:na:effect123"
        _, triggers, _ = parser.extract_triggers(text)
        assert triggers[0].sound_type == "effect123"


class TestSoundId:
    """Test sound ID tracking."""

    def test_play_stores_id(self, parser):
        """Play action should store sound ID in sound_type."""
        text = "$sphook play:effects/beep:100:1:0:beep123"
        _, triggers, _ = parser.extract_triggers(text)
        assert triggers[0].sound_type == "beep123"

    def test_loop_stores_id(self, parser):
        """Loop action should store sound ID in sound_type."""
        text = "$sphook loop:music/theme:100:1:0:theme456"
        _, triggers, _ = parser.extract_triggers(text)
        assert triggers[0].sound_type == "theme456"


class TestBufferAnnouncements:
    """Test $buffer announcement parsing."""

    def test_simple_buffer(self, parser):
        """Parse simple buffer announcement."""
        text = "$buffer Hello, world!"
        cleaned, triggers, announcements = parser.extract_triggers(text)
        assert len(announcements) == 1
        assert announcements[0].text == "Hello, world!"

    def test_buffer_removed_from_text(self, parser):
        """Buffer line should be removed from cleaned text."""
        text = "$buffer Announcement\nVisible text"
        cleaned, _, _ = parser.extract_triggers(text)
        assert "$buffer" not in cleaned
        assert "Visible text" in cleaned

    def test_multiple_buffers(self, parser):
        """Multiple buffer announcements should all be captured."""
        text = "$buffer First\n$buffer Second\n$buffer Third"
        _, _, announcements = parser.extract_triggers(text)
        assert len(announcements) == 3
        assert announcements[0].text == "First"
        assert announcements[1].text == "Second"
        assert announcements[2].text == "Third"

    def test_buffer_whitespace_stripped(self, parser):
        """Buffer text should have whitespace stripped."""
        text = "$buffer   Padded text   "
        _, _, announcements = parser.extract_triggers(text)
        assert announcements[0].text == "Padded text"


class TestTextCleaning:
    """Test that protocol lines are removed from output."""

    def test_sphook_removed(self, parser):
        """$sphook lines should be removed from text."""
        text = "Normal text\n$sphook play:test:100:1:0:id\nMore text"
        cleaned, _, _ = parser.extract_triggers(text)
        assert "$sphook" not in cleaned
        assert "Normal text" in cleaned
        assert "More text" in cleaned

    def test_soundpack_version_removed(self, parser):
        """$soundpack mudlet version lines should be removed."""
        text = "Text\n$soundpack mudlet last version: 123\nMore"
        cleaned, _, _ = parser.extract_triggers(text)
        assert "$soundpack" not in cleaned
        assert "Text" in cleaned

    def test_multiple_newlines_collapsed(self, parser):
        """Multiple consecutive newlines should be collapsed."""
        text = "$sphook play:test:100:1:0:id\n\n\n\nText"
        cleaned, _, _ = parser.extract_triggers(text)
        # Should not have multiple consecutive newlines
        assert "\n\n" not in cleaned

    def test_telnet_carriage_returns(self, parser):
        """Should handle telnet-style carriage returns."""
        text = "$sphook play:test:100:1:0:id\r\nMore text\r\n"
        cleaned, triggers, _ = parser.extract_triggers(text)
        assert len(triggers) == 1
        assert "More text" in cleaned


class TestMultipleTriggers:
    """Test multiple triggers in one text block."""

    def test_multiple_sphook_commands(self, parser):
        """Multiple $sphook commands should all be parsed."""
        text = "$sphook play:a:100:1:0:id1\n$sphook play:b:100:1:0:id2\n$sphook loop:c:50:1:0:id3"
        _, triggers, _ = parser.extract_triggers(text)
        assert len(triggers) == 3

    def test_mixed_commands(self, parser):
        """Mixed play, loop, and stop commands should all be parsed."""
        text = """$sphook play:effect:100:1:0:e1
$sphook loop:ambient:50:1:0:a1
$sphook stop:na:na:na:na:e1"""
        _, triggers, _ = parser.extract_triggers(text)
        assert len(triggers) == 3
        # First is play (loops=1)
        assert triggers[0].loops == 1
        # Second is loop (loops=-1)
        assert triggers[1].loops == -1
        # Third is stop
        assert triggers[2].is_stop is True


class TestSPHookState:
    """Test SPHookState for sound tracking."""

    def test_register_sound(self, parser):
        """Register a playing sound."""
        state = SPHookState()
        text = "$sphook play:test:100:1:0:sound123"
        _, triggers, _ = parser.extract_triggers(text)
        state.register_sound(triggers[0])
        assert "sound123" in state.get_active_sounds()

    def test_unregister_sound(self, parser):
        """Unregister a sound and get its filename."""
        state = SPHookState()
        text = "$sphook play:effects/boom:100:1:0:boom1"
        _, triggers, _ = parser.extract_triggers(text)
        state.register_sound(triggers[0])

        filename = state.unregister_sound("boom1")
        assert filename == "effects/boom.wav"
        assert "boom1" not in state.get_active_sounds()

    def test_unregister_nonexistent(self):
        """Unregistering nonexistent sound should return None."""
        state = SPHookState()
        result = state.unregister_sound("nonexistent")
        assert result is None

    def test_stop_not_registered(self, parser):
        """Stop commands should not be registered."""
        state = SPHookState()
        text = "$sphook stop:na:na:na:na:sound1"
        _, triggers, _ = parser.extract_triggers(text)
        state.register_sound(triggers[0])
        assert "sound1" not in state.get_active_sounds()


class TestBufferAnnouncementClass:
    """Test BufferAnnouncement dataclass."""

    def test_buffer_announcement_creation(self):
        """BufferAnnouncement should store text."""
        announcement = BufferAnnouncement(text="Test message")
        assert announcement.text == "Test message"


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_text(self, parser):
        """Empty text should return empty results."""
        cleaned, triggers, announcements = parser.extract_triggers("")
        assert cleaned == ""
        assert triggers == []
        assert announcements == []

    def test_no_protocol_lines(self, parser):
        """Text without protocol lines should pass through."""
        text = "Just regular MUD text here."
        cleaned, triggers, announcements = parser.extract_triggers(text)
        assert cleaned == text
        assert triggers == []
        assert announcements == []

    def test_invalid_action(self, parser):
        """Invalid action should not produce trigger."""
        text = "$sphook invalid:path:100:1:0:id"
        _, triggers, _ = parser.extract_triggers(text)
        assert len(triggers) == 0

    def test_malformed_sphook(self, parser):
        """Malformed $sphook should not match."""
        text = "$sphook play:only:two"  # Not enough fields
        _, triggers, _ = parser.extract_triggers(text)
        assert len(triggers) == 0

    def test_sphook_mid_line(self, parser):
        """$sphook must be at start of line."""
        text = "Some text $sphook play:test:100:1:0:id"
        _, triggers, _ = parser.extract_triggers(text)
        # Should still match since pattern has MULTILINE flag
        # and the regex starts with ^ which matches start of line
        assert len(triggers) == 0  # Actually won't match - no ^ in pattern

    def test_file_extension_without_dot(self):
        """Parser should handle extension without leading dot."""
        parser = SPHookParser(file_extension="ogg")
        text = "$sphook play:test:100:1:0:id"
        _, triggers, _ = parser.extract_triggers(text)
        assert triggers[0].filename == "test.ogg"

    def test_download_url_construction(self, parser):
        """Download URL should be correctly constructed."""
        text = "$sphook play:effects/explosion:80:1:0:boom"
        _, triggers, _ = parser.extract_triggers(text)
        # The download_url property combines url + filename
        expected = f"{COSMIC_RAGE_SOUND_URL}wav/effects/explosion.wav"
        assert triggers[0].download_url == expected
