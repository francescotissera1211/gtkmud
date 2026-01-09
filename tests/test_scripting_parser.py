"""Tests for the DSL parser."""

import pytest
from lark.exceptions import UnexpectedInput, UnexpectedToken

from gtkmud.scripting.parser import (
    DSLParser, Script, Trigger, Gag, Alias, SoundTrigger,
    SoundAction, SoundStopAction, AmbienceAction, SendAction,
    GagAction, HighlightAction, VarAction, IfAction,
    SoundOptions, AmbienceOptions, Pattern, ComparisonOp,
)


@pytest.fixture
def parser():
    """Create a DSL parser instance."""
    return DSLParser()


class TestBasicParsing:
    """Test basic parsing functionality."""

    def test_empty_script(self, parser):
        """Empty script should parse to empty Script."""
        script = parser.parse("")
        assert isinstance(script, Script)
        assert script.triggers == []
        assert script.gags == []
        assert script.aliases == []

    def test_comments_only(self, parser):
        """Comments should be ignored."""
        script = parser.parse("""
        # This is a comment
        # Another comment
        """)
        assert script.triggers == []

    def test_whitespace_handling(self, parser):
        """Whitespace should be handled correctly."""
        script = parser.parse("   \n\n   ")
        assert script.triggers == []


class TestAliases:
    """Test alias parsing."""

    def test_simple_alias(self, parser):
        """Parse a simple alias."""
        script = parser.parse('alias "n" "north"')
        assert len(script.aliases) == 1
        assert script.aliases[0].shortcut == "n"
        assert script.aliases[0].expansion == "north"

    def test_multiple_aliases(self, parser):
        """Parse multiple aliases."""
        script = parser.parse('''
        alias "n" "north"
        alias "s" "south"
        alias "e" "east"
        alias "w" "west"
        ''')
        assert len(script.aliases) == 4
        assert script.aliases[0].shortcut == "n"
        assert script.aliases[3].shortcut == "w"

    def test_alias_with_spaces(self, parser):
        """Parse alias with spaces in expansion."""
        script = parser.parse('alias "ga" "get all"')
        assert script.aliases[0].expansion == "get all"

    def test_alias_with_escapes(self, parser):
        """Parse alias with escape sequences."""
        script = parser.parse('alias "test" "say \\"hello\\""')
        assert script.aliases[0].expansion == 'say "hello"'


class TestGags:
    """Test gag parsing."""

    def test_literal_gag(self, parser):
        """Parse a literal string gag."""
        script = parser.parse('gag "You feel tired"')
        assert len(script.gags) == 1
        assert script.gags[0].pattern.pattern == "You feel tired"
        assert script.gags[0].pattern.is_regex is False

    def test_regex_gag(self, parser):
        """Parse a regex gag."""
        script = parser.parse('gag /^\\[OOC\\]/')
        assert len(script.gags) == 1
        assert script.gags[0].pattern.is_regex is True

    def test_case_insensitive_regex_gag(self, parser):
        """Parse case-insensitive regex gag."""
        script = parser.parse('gag /spam/i')
        assert script.gags[0].pattern.case_insensitive is True

    def test_multiple_gags(self, parser):
        """Parse multiple gags."""
        script = parser.parse('''
        gag "spam message"
        gag /^\\[AutoSave\\]/
        ''')
        assert len(script.gags) == 2


class TestTriggers:
    """Test trigger parsing."""

    def test_simple_trigger(self, parser):
        """Parse a simple trigger with one action."""
        script = parser.parse('''
        trigger "Combat begins" {
            sound "battle.wav"
        }
        ''')
        assert len(script.triggers) == 1
        assert script.triggers[0].pattern.pattern == "Combat begins"
        assert len(script.triggers[0].actions) == 1
        assert isinstance(script.triggers[0].actions[0], SoundAction)

    def test_regex_trigger(self, parser):
        """Parse a regex trigger."""
        script = parser.parse('''
        trigger /^(\\w+) tells you/ {
            sound "tell.wav"
        }
        ''')
        assert script.triggers[0].pattern.is_regex is True
        assert script.triggers[0].pattern.pattern == r"^(\w+) tells you"

    def test_trigger_with_multiple_actions(self, parser):
        """Parse trigger with multiple actions."""
        script = parser.parse('''
        trigger "You win" {
            sound "victory.wav"
            send "celebrate"
        }
        ''')
        assert len(script.triggers[0].actions) == 2
        assert isinstance(script.triggers[0].actions[0], SoundAction)
        assert isinstance(script.triggers[0].actions[1], SendAction)

    def test_trigger_with_gag(self, parser):
        """Parse trigger with gag action."""
        script = parser.parse('''
        trigger "spam" {
            gag
        }
        ''')
        assert isinstance(script.triggers[0].actions[0], GagAction)

    def test_trigger_with_highlight(self, parser):
        """Parse trigger with highlight action."""
        script = parser.parse('''
        trigger "important" {
            highlight red
        }
        ''')
        assert isinstance(script.triggers[0].actions[0], HighlightAction)
        assert script.triggers[0].actions[0].color == "red"


class TestSoundActions:
    """Test sound action parsing."""

    def test_simple_sound(self, parser):
        """Parse simple sound action."""
        script = parser.parse('''
        trigger "test" {
            sound "beep.wav"
        }
        ''')
        action = script.triggers[0].actions[0]
        assert isinstance(action, SoundAction)
        assert action.filename == "beep.wav"
        assert action.options.volume == 100  # default
        assert action.options.loops == 1  # default

    def test_sound_with_volume(self, parser):
        """Parse sound with volume option."""
        script = parser.parse('''
        trigger "test" {
            sound "beep.wav" volume 50
        }
        ''')
        action = script.triggers[0].actions[0]
        assert action.options.volume == 50

    def test_sound_with_loop(self, parser):
        """Parse sound with loop count."""
        script = parser.parse('''
        trigger "test" {
            sound "beep.wav" loop 3
        }
        ''')
        action = script.triggers[0].actions[0]
        assert action.options.loops == 3

    def test_sound_with_infinite_loop(self, parser):
        """Parse sound with infinite loop."""
        script = parser.parse('''
        trigger "test" {
            sound "ambient.wav" loop infinite
        }
        ''')
        action = script.triggers[0].actions[0]
        assert action.options.loops == -1

    def test_sound_with_priority(self, parser):
        """Parse sound with priority."""
        script = parser.parse('''
        trigger "test" {
            sound "alert.wav" priority 90
        }
        ''')
        action = script.triggers[0].actions[0]
        assert action.options.priority == 90

    def test_sound_with_id(self, parser):
        """Parse sound with ID for stop tracking."""
        script = parser.parse('''
        trigger "test" {
            sound "charging.wav" id "charge1" loop infinite
        }
        ''')
        action = script.triggers[0].actions[0]
        assert action.options.id == "charge1"
        assert action.options.loops == -1

    def test_sound_with_all_options(self, parser):
        """Parse sound with all options."""
        script = parser.parse('''
        trigger "test" {
            sound "effect.wav" volume 80 loop 2 priority 75 id "effect1"
        }
        ''')
        action = script.triggers[0].actions[0]
        assert action.options.volume == 80
        assert action.options.loops == 2
        assert action.options.priority == 75
        assert action.options.id == "effect1"

    def test_sound_stop(self, parser):
        """Parse sound stop action."""
        script = parser.parse('''
        trigger "test" {
            sound stop
        }
        ''')
        action = script.triggers[0].actions[0]
        assert isinstance(action, SoundStopAction)
        assert action.sound_id is None

    def test_sound_stop_with_id(self, parser):
        """Parse sound stop with specific ID."""
        script = parser.parse('''
        trigger "test" {
            sound stop "charge1"
        }
        ''')
        action = script.triggers[0].actions[0]
        assert isinstance(action, SoundStopAction)
        assert action.sound_id == "charge1"


class TestAmbienceActions:
    """Test ambience action parsing."""

    def test_simple_ambience(self, parser):
        """Parse simple ambience action."""
        script = parser.parse('''
        trigger "test" {
            ambience "forest.wav"
        }
        ''')
        action = script.triggers[0].actions[0]
        assert isinstance(action, AmbienceAction)
        assert action.filename == "forest.wav"

    def test_ambience_with_loop(self, parser):
        """Parse ambience with loop option."""
        script = parser.parse('''
        trigger "test" {
            ambience "rain.wav" loop
        }
        ''')
        action = script.triggers[0].actions[0]
        assert action.options.loop is True

    def test_ambience_with_volume(self, parser):
        """Parse ambience with volume."""
        script = parser.parse('''
        trigger "test" {
            ambience "wind.wav" volume 60
        }
        ''')
        action = script.triggers[0].actions[0]
        assert action.options.volume == 60

    def test_ambience_with_fadein(self, parser):
        """Parse ambience with fade in."""
        script = parser.parse('''
        trigger "test" {
            ambience "music.wav" fadein 2000
        }
        ''')
        action = script.triggers[0].actions[0]
        assert action.options.fadein == 2000

    def test_ambience_stop(self, parser):
        """Parse ambience stop action."""
        script = parser.parse('''
        trigger "test" {
            ambience stop
        }
        ''')
        action = script.triggers[0].actions[0]
        assert isinstance(action, AmbienceAction)
        assert action.filename is None


class TestSendActions:
    """Test send action parsing."""

    def test_simple_send(self, parser):
        """Parse simple send action."""
        script = parser.parse('''
        trigger "test" {
            send "north"
        }
        ''')
        action = script.triggers[0].actions[0]
        assert isinstance(action, SendAction)

    def test_send_with_concatenation(self, parser):
        """Parse send with string concatenation."""
        script = parser.parse('''
        trigger "test" {
            send "say " + "hello"
        }
        ''')
        action = script.triggers[0].actions[0]
        assert isinstance(action, SendAction)


class TestVariables:
    """Test variable parsing."""

    def test_top_level_variable(self, parser):
        """Parse top-level variable assignment."""
        script = parser.parse('$combat = "false"')
        assert "combat" in script.variables
        assert script.variables["combat"] == "false"

    def test_variable_in_trigger(self, parser):
        """Parse variable assignment in trigger."""
        script = parser.parse('''
        trigger "Combat begins" {
            $combat = "true"
        }
        ''')
        action = script.triggers[0].actions[0]
        assert isinstance(action, VarAction)
        assert action.name == "combat"


class TestConditionals:
    """Test conditional (if/else) parsing."""

    def test_simple_if(self, parser):
        """Parse simple if statement."""
        script = parser.parse('''
        trigger "test" {
            if $combat == "true" {
                sound "battle.wav"
            }
        }
        ''')
        action = script.triggers[0].actions[0]
        assert isinstance(action, IfAction)
        assert action.condition.left_var == "combat"
        assert action.condition.op == ComparisonOp.EQ
        assert action.condition.right == "true"

    def test_if_else(self, parser):
        """Parse if-else statement."""
        script = parser.parse('''
        trigger "test" {
            if $state == "active" {
                sound "active.wav"
            } else {
                sound "inactive.wav"
            }
        }
        ''')
        action = script.triggers[0].actions[0]
        assert isinstance(action, IfAction)
        assert len(action.then_actions) == 1
        assert len(action.else_actions) == 1

    def test_if_with_match(self, parser):
        """Parse if with match() condition."""
        script = parser.parse('''
        trigger /^(\\w+) says/ {
            if match(1) != "" {
                sound "chat.wav"
            }
        }
        ''')
        action = script.triggers[0].actions[0]
        assert action.condition.match_group == 1
        assert action.condition.op == ComparisonOp.NE

    def test_comparison_operators(self, parser):
        """Test all comparison operators."""
        operators = [
            ('==', ComparisonOp.EQ),
            ('!=', ComparisonOp.NE),
            ('>', ComparisonOp.GT),
            ('<', ComparisonOp.LT),
            ('>=', ComparisonOp.GE),
            ('<=', ComparisonOp.LE),
        ]
        for op_str, op_enum in operators:
            script = parser.parse(f'''
            trigger "test" {{
                if $val {op_str} "10" {{
                    send "ok"
                }}
            }}
            ''')
            assert script.triggers[0].actions[0].condition.op == op_enum


class TestSoundTriggers:
    """Test sound_trigger shorthand parsing."""

    def test_simple_sound_trigger(self, parser):
        """Parse simple sound_trigger."""
        script = parser.parse('sound_trigger "combat" "battle.wav"')
        assert len(script.sound_triggers) == 1
        assert script.sound_triggers[0].filename == "battle.wav"
        assert script.sound_triggers[0].pattern.pattern == "combat"

    def test_regex_sound_trigger(self, parser):
        """Parse regex sound_trigger."""
        script = parser.parse('sound_trigger /^\\w+ tells you/ "tell.wav"')
        assert script.sound_triggers[0].pattern.is_regex is True

    def test_sound_trigger_with_options(self, parser):
        """Parse sound_trigger with options."""
        script = parser.parse('sound_trigger "alert" "alert.wav" volume 80 priority 90')
        assert script.sound_triggers[0].options.volume == 80
        assert script.sound_triggers[0].options.priority == 90


class TestPatternMatching:
    """Test pattern compilation and matching."""

    def test_literal_pattern_match(self, parser):
        """Test literal pattern matching."""
        script = parser.parse('gag "test message"')
        pattern = script.gags[0].pattern
        assert pattern.match("This is a test message here")
        assert not pattern.match("no match here")

    def test_regex_pattern_match(self, parser):
        """Test regex pattern matching."""
        script = parser.parse('gag /^\\[OOC\\]/')
        pattern = script.gags[0].pattern
        assert pattern.match("[OOC] Hello")
        assert not pattern.match("Not [OOC]")

    def test_case_insensitive_match(self, parser):
        """Test case-insensitive regex matching."""
        script = parser.parse('gag /hello/i')
        pattern = script.gags[0].pattern
        assert pattern.match("HELLO")
        assert pattern.match("Hello")
        assert pattern.match("hello")


class TestParseErrors:
    """Test parser error handling."""

    def test_unclosed_string(self, parser):
        """Unclosed string should raise error."""
        with pytest.raises((UnexpectedInput, UnexpectedToken)):
            parser.parse('alias "test')

    def test_missing_block(self, parser):
        """Missing block should raise error."""
        with pytest.raises((UnexpectedInput, UnexpectedToken)):
            parser.parse('trigger "test"')

    def test_invalid_syntax(self, parser):
        """Invalid syntax should raise error."""
        with pytest.raises((UnexpectedInput, UnexpectedToken)):
            parser.parse('invalid syntax here')
