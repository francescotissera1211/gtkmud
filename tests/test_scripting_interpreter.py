"""Tests for the script interpreter."""

import pytest

from gtkmud.scripting.parser import DSLParser
from gtkmud.scripting.interpreter import ScriptInterpreter, TriggerResult


@pytest.fixture
def parser():
    """Create a DSL parser instance."""
    return DSLParser()


@pytest.fixture
def interpreter():
    """Create an interpreter with no script."""
    return ScriptInterpreter()


def make_interpreter(parser, script_text):
    """Helper to create an interpreter with a parsed script."""
    script = parser.parse(script_text)
    return ScriptInterpreter(script)


class TestAliasExpansion:
    """Test alias expansion."""

    def test_exact_match_alias(self, parser):
        """Alias should expand on exact match."""
        interp = make_interpreter(parser, 'alias "n" "north"')
        assert interp.expand_alias("n") == "north"

    def test_alias_with_args(self, parser):
        """Alias should pass through extra arguments."""
        interp = make_interpreter(parser, 'alias "t" "tell"')
        assert interp.expand_alias("t bob hello") == "tell bob hello"

    def test_no_alias_match(self, parser):
        """Non-matching input should return unchanged."""
        interp = make_interpreter(parser, 'alias "n" "north"')
        assert interp.expand_alias("south") == "south"

    def test_alias_not_prefix_match(self, parser):
        """Alias should not match as prefix without space."""
        interp = make_interpreter(parser, 'alias "n" "north"')
        assert interp.expand_alias("northwest") == "northwest"

    def test_multiple_aliases(self, parser):
        """Multiple aliases should all work."""
        interp = make_interpreter(parser, '''
        alias "n" "north"
        alias "s" "south"
        ''')
        assert interp.expand_alias("n") == "north"
        assert interp.expand_alias("s") == "south"


class TestGagChecking:
    """Test gag/suppress checking."""

    def test_literal_gag_match(self, parser):
        """Literal gag should match containing text."""
        interp = make_interpreter(parser, 'gag "spam message"')
        assert interp.check_gag("This is a spam message here")
        assert not interp.check_gag("no match")

    def test_regex_gag_match(self, parser):
        """Regex gag should match pattern."""
        interp = make_interpreter(parser, 'gag /^\\[OOC\\]/')
        assert interp.check_gag("[OOC] Hello everyone")
        assert not interp.check_gag("Not at start [OOC]")

    def test_no_gag_match(self, parser):
        """Non-matching text should not be gagged."""
        interp = make_interpreter(parser, 'gag "specific text"')
        assert not interp.check_gag("completely different")

    def test_multiple_gags(self, parser):
        """Any matching gag should trigger."""
        interp = make_interpreter(parser, '''
        gag "spam"
        gag "junk"
        ''')
        assert interp.check_gag("spam message")
        assert interp.check_gag("junk message")
        assert not interp.check_gag("normal message")


class TestTriggerProcessing:
    """Test trigger execution."""

    def test_trigger_sound(self, parser):
        """Trigger should add sound to result."""
        interp = make_interpreter(parser, '''
        trigger "combat" {
            sound "battle.wav"
        }
        ''')
        result = interp.process_line("combat starts")
        assert len(result.sounds_to_play) == 1
        assert result.sounds_to_play[0][0] == "battle.wav"

    def test_trigger_no_match(self, parser):
        """Non-matching line should have no sounds."""
        interp = make_interpreter(parser, '''
        trigger "combat" {
            sound "battle.wav"
        }
        ''')
        result = interp.process_line("peaceful scene")
        assert len(result.sounds_to_play) == 0

    def test_trigger_gag_action(self, parser):
        """Gag action should set should_gag."""
        interp = make_interpreter(parser, '''
        trigger "spam" {
            gag
        }
        ''')
        result = interp.process_line("spam message")
        assert result.should_gag is True

    def test_trigger_highlight(self, parser):
        """Highlight action should set highlight_color."""
        interp = make_interpreter(parser, '''
        trigger "important" {
            highlight red
        }
        ''')
        result = interp.process_line("important notice")
        assert result.highlight_color == "red"

    def test_trigger_ambience(self, parser):
        """Ambience action should set ambience."""
        interp = make_interpreter(parser, '''
        trigger "forest" {
            ambience "forest.wav" volume 60
        }
        ''')
        result = interp.process_line("You enter the forest")
        assert result.ambience is not None
        assert result.ambience[0] == "forest.wav"
        assert result.ambience[1]["volume"] == 60

    def test_trigger_ambience_stop(self, parser):
        """Ambience stop should set ambience to None."""
        interp = make_interpreter(parser, '''
        trigger "leave" {
            ambience stop
        }
        ''')
        result = interp.process_line("You leave the area")
        assert result.ambience == (None, {})

    def test_multiple_triggers(self, parser):
        """Multiple matching triggers should all fire."""
        interp = make_interpreter(parser, '''
        trigger "combat" {
            sound "alert.wav"
        }
        trigger /combat/ {
            sound "battle.wav"
        }
        ''')
        result = interp.process_line("combat begins")
        assert len(result.sounds_to_play) == 2

    def test_sound_stop_action(self, parser):
        """Sound stop should add to sounds_to_stop."""
        interp = make_interpreter(parser, '''
        trigger "stop charging" {
            sound stop "charge1"
        }
        ''')
        result = interp.process_line("stop charging")
        assert len(result.sounds_to_stop) == 1
        assert result.sounds_to_stop[0] == "charge1"

    def test_sound_stop_all(self, parser):
        """Sound stop without ID should add None."""
        interp = make_interpreter(parser, '''
        trigger "silence" {
            sound stop
        }
        ''')
        result = interp.process_line("silence please")
        assert len(result.sounds_to_stop) == 1
        assert result.sounds_to_stop[0] is None


class TestSoundTriggers:
    """Test sound_trigger shorthand."""

    def test_sound_trigger_match(self, parser):
        """sound_trigger should add sound on match."""
        interp = make_interpreter(parser, 'sound_trigger "tell" "tell.wav" volume 80')
        result = interp.process_line("Someone tells you hello")
        assert len(result.sounds_to_play) == 1
        assert result.sounds_to_play[0][0] == "tell.wav"
        assert result.sounds_to_play[0][1]["volume"] == 80

    def test_sound_trigger_regex(self, parser):
        """sound_trigger with regex should work."""
        interp = make_interpreter(parser, 'sound_trigger /^\\w+ says/ "chat.wav"')
        result = interp.process_line("Bob says hello")
        assert len(result.sounds_to_play) == 1


class TestVariables:
    """Test variable management."""

    def test_initial_variables(self, parser):
        """Variables defined at top level should be available."""
        interp = make_interpreter(parser, '$combat = "false"')
        assert interp.get_variable("combat") == "false"

    def test_variable_set_in_trigger(self, parser):
        """Variables set in triggers should persist."""
        interp = make_interpreter(parser, '''
        $combat = "false"
        trigger "Combat begins" {
            $combat = "true"
        }
        ''')
        assert interp.get_variable("combat") == "false"
        interp.process_line("Combat begins now")
        assert interp.get_variable("combat") == "true"

    def test_get_nonexistent_variable(self, parser):
        """Getting nonexistent variable should return empty string."""
        interp = make_interpreter(parser, '')
        assert interp.get_variable("nonexistent") == ""

    def test_set_variable(self, parser):
        """set_variable should update value."""
        interp = make_interpreter(parser, '')
        interp.set_variable("test", "value")
        assert interp.get_variable("test") == "value"


class TestConditionals:
    """Test conditional execution."""

    def test_if_true_branch(self, parser):
        """If condition true should execute then branch."""
        interp = make_interpreter(parser, '''
        $state = "active"
        trigger "test" {
            if $state == "active" {
                sound "active.wav"
            } else {
                sound "inactive.wav"
            }
        }
        ''')
        result = interp.process_line("test condition")
        assert len(result.sounds_to_play) == 1
        assert result.sounds_to_play[0][0] == "active.wav"

    def test_if_false_branch(self, parser):
        """If condition false should execute else branch."""
        interp = make_interpreter(parser, '''
        $state = "inactive"
        trigger "test" {
            if $state == "active" {
                sound "active.wav"
            } else {
                sound "inactive.wav"
            }
        }
        ''')
        result = interp.process_line("test condition")
        assert len(result.sounds_to_play) == 1
        assert result.sounds_to_play[0][0] == "inactive.wav"

    def test_if_no_else(self, parser):
        """If without else and false condition should do nothing."""
        interp = make_interpreter(parser, '''
        $state = "inactive"
        trigger "test" {
            if $state == "active" {
                sound "active.wav"
            }
        }
        ''')
        result = interp.process_line("test condition")
        assert len(result.sounds_to_play) == 0

    def test_numeric_comparison(self, parser):
        """Numeric comparisons should work."""
        interp = make_interpreter(parser, '''
        $health = "30"
        trigger "check" {
            if $health < "50" {
                sound "lowhealth.wav"
            }
        }
        ''')
        result = interp.process_line("check health")
        assert len(result.sounds_to_play) == 1
        assert result.sounds_to_play[0][0] == "lowhealth.wav"

    def test_not_equal(self, parser):
        """Not equal comparison should work."""
        interp = make_interpreter(parser, '''
        $mode = "combat"
        trigger "test" {
            if $mode != "peaceful" {
                sound "alert.wav"
            }
        }
        ''')
        result = interp.process_line("test mode")
        assert len(result.sounds_to_play) == 1


class TestRegexCaptures:
    """Test regex capture group access."""

    def test_match_group_in_send(self, parser):
        """match() should access capture groups in send."""
        interp = make_interpreter(parser, '''
        trigger /^(\\w+) tells you '(.+)'$/ {
            send "reply " + match(1)
        }
        ''')
        # Set up callback to capture sent command
        sent = []
        interp.on_send = lambda cmd: sent.append(cmd)

        interp.process_line("Bob tells you 'hello'")
        assert len(sent) == 1
        assert sent[0] == "reply Bob"

    def test_match_in_condition(self, parser):
        """match() should work in conditions."""
        interp = make_interpreter(parser, '''
        trigger /^(\\w+) attacks/ {
            if match(1) != "" {
                sound "combat.wav"
            }
        }
        ''')
        result = interp.process_line("Dragon attacks you")
        assert len(result.sounds_to_play) == 1


class TestCallbacks:
    """Test interpreter callbacks."""

    def test_on_send_callback(self, parser):
        """on_send should be called for send actions."""
        interp = make_interpreter(parser, '''
        trigger "go" {
            send "north"
        }
        ''')
        sent = []
        interp.on_send = lambda cmd: sent.append(cmd)

        interp.process_line("go now")
        assert sent == ["north"]

    def test_on_sound_callback(self, parser):
        """on_sound should be called for sound actions."""
        interp = make_interpreter(parser, '''
        trigger "alert" {
            sound "alert.wav" volume 80
        }
        ''')
        sounds = []
        interp.on_sound = lambda f, o: sounds.append((f, o))

        interp.process_line("alert!")
        assert len(sounds) == 1
        assert sounds[0][0] == "alert.wav"
        assert sounds[0][1]["volume"] == 80

    def test_on_sound_stop_callback(self, parser):
        """on_sound_stop should be called for sound stop actions."""
        interp = make_interpreter(parser, '''
        trigger "stop" {
            sound stop "effect1"
        }
        ''')
        stopped = []
        interp.on_sound_stop = lambda sid: stopped.append(sid)

        interp.process_line("stop sound")
        assert stopped == ["effect1"]

    def test_on_ambience_callback(self, parser):
        """on_ambience should be called for ambience actions."""
        interp = make_interpreter(parser, '''
        trigger "forest" {
            ambience "forest.wav" volume 60
        }
        ''')
        ambiences = []
        interp.on_ambience = lambda f, o: ambiences.append((f, o))

        interp.process_line("enter forest")
        assert len(ambiences) == 1
        assert ambiences[0][0] == "forest.wav"


class TestTriggerResult:
    """Test TriggerResult dataclass."""

    def test_default_values(self):
        """TriggerResult should have correct defaults."""
        result = TriggerResult()
        assert result.should_gag is False
        assert result.highlight_color is None
        assert result.commands_to_send == []
        assert result.sounds_to_play == []
        assert result.sounds_to_stop == []
        assert result.ambience is None
