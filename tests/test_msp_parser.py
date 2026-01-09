"""Tests for the MSP (MUD Sound Protocol) parser."""

import pytest

from gtkmud.parsers.msp import MSPParser, SoundTrigger, MSPState


@pytest.fixture
def parser():
    """Create an MSP parser instance."""
    return MSPParser()


class TestSoundTriggerParsing:
    """Test !!SOUND() trigger parsing."""

    def test_simple_sound(self, parser):
        """Parse simple sound trigger."""
        text = "!!SOUND(explosion.wav)"
        cleaned, triggers = parser.extract_triggers(text)
        assert len(triggers) == 1
        assert triggers[0].type == "sound"
        assert triggers[0].filename == "explosion.wav"

    def test_sound_with_volume(self, parser):
        """Parse sound with volume parameter."""
        text = "!!SOUND(beep.wav V=80)"
        cleaned, triggers = parser.extract_triggers(text)
        assert triggers[0].volume == 80

    def test_sound_with_loops(self, parser):
        """Parse sound with loop parameter."""
        text = "!!SOUND(ambient.wav L=3)"
        cleaned, triggers = parser.extract_triggers(text)
        assert triggers[0].loops == 3

    def test_sound_with_infinite_loop(self, parser):
        """Parse sound with infinite loop."""
        text = "!!SOUND(background.wav L=-1)"
        cleaned, triggers = parser.extract_triggers(text)
        assert triggers[0].loops == -1

    def test_sound_with_priority(self, parser):
        """Parse sound with priority parameter."""
        text = "!!SOUND(alert.wav P=90)"
        cleaned, triggers = parser.extract_triggers(text)
        assert triggers[0].priority == 90

    def test_sound_with_type(self, parser):
        """Parse sound with type parameter."""
        text = "!!SOUND(hit.wav T=combat)"
        cleaned, triggers = parser.extract_triggers(text)
        assert triggers[0].sound_type == "combat"

    def test_sound_with_url(self, parser):
        """Parse sound with URL parameter."""
        text = "!!SOUND(effect.wav U=http://example.com/sounds/)"
        cleaned, triggers = parser.extract_triggers(text)
        assert triggers[0].url == "http://example.com/sounds/"

    def test_sound_with_all_params(self, parser):
        """Parse sound with all parameters."""
        text = "!!SOUND(battle.wav V=75 L=2 P=80 T=combat U=http://mud.com/)"
        cleaned, triggers = parser.extract_triggers(text)
        trigger = triggers[0]
        assert trigger.filename == "battle.wav"
        assert trigger.volume == 75
        assert trigger.loops == 2
        assert trigger.priority == 80
        assert trigger.sound_type == "combat"
        assert trigger.url == "http://mud.com/"

    def test_sound_off(self, parser):
        """Parse sound stop command."""
        text = "!!SOUND(Off)"
        cleaned, triggers = parser.extract_triggers(text)
        assert triggers[0].is_stop is True

    def test_sound_off_case_insensitive(self, parser):
        """Sound Off should be case insensitive."""
        text = "!!SOUND(off)"
        cleaned, triggers = parser.extract_triggers(text)
        assert triggers[0].is_stop is True

        text = "!!SOUND(OFF)"
        cleaned, triggers = parser.extract_triggers(text)
        assert triggers[0].is_stop is True


class TestMusicTriggerParsing:
    """Test !!MUSIC() trigger parsing."""

    def test_simple_music(self, parser):
        """Parse simple music trigger."""
        text = "!!MUSIC(theme.mp3)"
        cleaned, triggers = parser.extract_triggers(text)
        assert len(triggers) == 1
        assert triggers[0].type == "music"
        assert triggers[0].filename == "theme.mp3"

    def test_music_with_volume(self, parser):
        """Parse music with volume."""
        text = "!!MUSIC(background.mp3 V=50)"
        cleaned, triggers = parser.extract_triggers(text)
        assert triggers[0].volume == 50

    def test_music_with_continue(self, parser):
        """Parse music with continue parameter."""
        text = "!!MUSIC(theme.mp3 C=1)"
        cleaned, triggers = parser.extract_triggers(text)
        assert triggers[0].continue_ is True

        text = "!!MUSIC(theme.mp3 C=0)"
        cleaned, triggers = parser.extract_triggers(text)
        assert triggers[0].continue_ is False

    def test_music_off(self, parser):
        """Parse music stop command."""
        text = "!!MUSIC(Off)"
        cleaned, triggers = parser.extract_triggers(text)
        assert triggers[0].is_stop is True


class TestTextCleaning:
    """Test that triggers are removed from text."""

    def test_sound_removed(self, parser):
        """Sound trigger should be removed from text."""
        text = "!!SOUND(beep.wav)\nSome text"
        cleaned, triggers = parser.extract_triggers(text)
        assert "!!SOUND" not in cleaned
        assert "Some text" in cleaned

    def test_music_removed(self, parser):
        """Music trigger should be removed from text."""
        text = "Welcome!\n!!MUSIC(intro.mp3)\nEnjoy!"
        cleaned, triggers = parser.extract_triggers(text)
        assert "!!MUSIC" not in cleaned
        assert "Welcome!" in cleaned
        assert "Enjoy!" in cleaned

    def test_multiple_triggers_removed(self, parser):
        """Multiple triggers should all be removed."""
        text = "!!SOUND(a.wav)\n!!MUSIC(b.mp3)\nText"
        cleaned, triggers = parser.extract_triggers(text)
        assert len(triggers) == 2
        assert "!!SOUND" not in cleaned
        assert "!!MUSIC" not in cleaned


class TestTriggerPosition:
    """Test trigger position requirements."""

    def test_trigger_at_start_of_line(self, parser):
        """Trigger at start of line should be parsed."""
        text = "!!SOUND(beep.wav)"
        cleaned, triggers = parser.extract_triggers(text)
        assert len(triggers) == 1

    def test_trigger_after_newline(self, parser):
        """Trigger after newline should be parsed."""
        text = "Some text\n!!SOUND(beep.wav)"
        cleaned, triggers = parser.extract_triggers(text)
        assert len(triggers) == 1


class TestSoundTriggerProperties:
    """Test SoundTrigger properties."""

    def test_is_stop_true(self):
        """is_stop should be True for 'off'."""
        trigger = SoundTrigger(type="sound", filename="off")
        assert trigger.is_stop is True

        trigger = SoundTrigger(type="sound", filename="Off")
        assert trigger.is_stop is True

    def test_is_stop_false(self):
        """is_stop should be False for normal files."""
        trigger = SoundTrigger(type="sound", filename="beep.wav")
        assert trigger.is_stop is False

    def test_download_url(self):
        """download_url should combine base URL and filename."""
        trigger = SoundTrigger(
            type="sound",
            filename="effect.wav",
            url="http://example.com/sounds/"
        )
        assert trigger.download_url == "http://example.com/sounds/effect.wav"

    def test_download_url_trailing_slash(self):
        """download_url should handle trailing slash."""
        trigger = SoundTrigger(
            type="sound",
            filename="effect.wav",
            url="http://example.com/sounds"  # No trailing slash
        )
        assert trigger.download_url == "http://example.com/sounds/effect.wav"

    def test_download_url_none_for_stop(self):
        """download_url should be None for stop commands."""
        trigger = SoundTrigger(type="sound", filename="off", url="http://x.com/")
        assert trigger.download_url is None

    def test_download_url_none_without_url(self):
        """download_url should be None without URL."""
        trigger = SoundTrigger(type="sound", filename="beep.wav")
        assert trigger.download_url is None


class TestMSPState:
    """Test MSP state management."""

    def test_default_url_from_stop(self):
        """Stop command with URL should set default."""
        state = MSPState()
        trigger = SoundTrigger(
            type="sound",
            filename="off",
            url="http://example.com/sounds/"
        )
        state.apply_trigger(trigger)
        assert state.default_sound_url == "http://example.com/sounds/"

    def test_apply_default_url(self):
        """Trigger without URL should get default."""
        state = MSPState()
        state.default_sound_url = "http://example.com/sounds/"

        trigger = SoundTrigger(type="sound", filename="beep.wav")
        updated = state.apply_trigger(trigger)
        assert updated.url == "http://example.com/sounds/"

    def test_music_default_url(self):
        """Music should have separate default URL."""
        state = MSPState()
        trigger = SoundTrigger(
            type="music",
            filename="off",
            url="http://example.com/music/"
        )
        state.apply_trigger(trigger)
        assert state.default_music_url == "http://example.com/music/"
        assert state.default_sound_url == ""


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_volume_clamped(self, parser):
        """Volume should be clamped to 0-100."""
        text = "!!SOUND(beep.wav V=150)"
        cleaned, triggers = parser.extract_triggers(text)
        assert triggers[0].volume == 100

        text = "!!SOUND(beep.wav V=-50)"
        cleaned, triggers = parser.extract_triggers(text)
        assert triggers[0].volume == 0

    def test_priority_clamped(self, parser):
        """Priority should be clamped to 0-100."""
        text = "!!SOUND(beep.wav P=200)"
        cleaned, triggers = parser.extract_triggers(text)
        assert triggers[0].priority == 100

    def test_invalid_volume_ignored(self, parser):
        """Invalid volume value should use default."""
        text = "!!SOUND(beep.wav V=abc)"
        cleaned, triggers = parser.extract_triggers(text)
        assert triggers[0].volume == 100  # default

    def test_empty_trigger(self, parser):
        """Empty trigger content should return None."""
        text = "!!SOUND()"
        cleaned, triggers = parser.extract_triggers(text)
        assert len(triggers) == 0

    def test_case_insensitive_params(self, parser):
        """Parameter names should be case insensitive."""
        text = "!!SOUND(beep.wav v=50 l=2)"
        cleaned, triggers = parser.extract_triggers(text)
        assert triggers[0].volume == 50
        assert triggers[0].loops == 2

    def test_case_insensitive_trigger(self, parser):
        """Trigger name should be case insensitive."""
        text = "!!sound(beep.wav)"
        cleaned, triggers = parser.extract_triggers(text)
        assert len(triggers) == 1

        text = "!!SOUND(beep.wav)"
        cleaned, triggers = parser.extract_triggers(text)
        assert len(triggers) == 1

    def test_no_triggers(self, parser):
        """Text without triggers should return empty list."""
        text = "Just some normal text"
        cleaned, triggers = parser.extract_triggers(text)
        assert len(triggers) == 0
        assert cleaned == text
