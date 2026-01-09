"""DSL parser using Lark."""

import re
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Union
from enum import Enum, auto

from lark import Lark, Transformer, v_args

logger = logging.getLogger(__name__)

# Load grammar from file
GRAMMAR_PATH = Path(__file__).parent / "grammar.lark"


class ComparisonOp(Enum):
    """Comparison operators."""
    EQ = auto()
    NE = auto()
    GT = auto()
    LT = auto()
    GE = auto()
    LE = auto()


@dataclass
class Pattern:
    """A match pattern (literal string or regex)."""
    pattern: str
    is_regex: bool = False
    case_insensitive: bool = False
    _compiled: Optional[re.Pattern] = field(default=None, repr=False)

    def compile(self) -> re.Pattern:
        """Compile the pattern to a regex."""
        if self._compiled is not None:
            return self._compiled

        if self.is_regex:
            flags = re.IGNORECASE if self.case_insensitive else 0
            self._compiled = re.compile(self.pattern, flags)
        else:
            # Escape literal string and compile
            escaped = re.escape(self.pattern)
            self._compiled = re.compile(escaped)

        return self._compiled

    def match(self, text: str) -> Optional[re.Match]:
        """Match pattern against text."""
        return self.compile().search(text)


@dataclass
class SoundOptions:
    """Options for sound playback."""
    volume: int = 100
    loops: int = 1
    priority: int = 50
    id: Optional[str] = None  # Optional ID for stop tracking


@dataclass
class AmbienceOptions:
    """Options for ambience playback."""
    loop: bool = True
    volume: int = 100
    fadein: int = 0


@dataclass
class Condition:
    """A conditional expression."""
    left_var: Optional[str] = None  # Variable name or None for match
    match_group: Optional[int] = None  # Match group number
    op: ComparisonOp = ComparisonOp.EQ
    right: str = ""  # Right-hand value


@dataclass
class Expression:
    """An expression that can be evaluated."""
    parts: list  # List of (type, value) tuples


# Action types
@dataclass
class SendAction:
    """Send command to server."""
    expression: Expression


@dataclass
class SoundAction:
    """Play a sound."""
    filename: str
    options: SoundOptions = field(default_factory=SoundOptions)


@dataclass
class SoundStopAction:
    """Stop a sound by ID or all sounds."""
    sound_id: Optional[str] = None  # None means stop all sounds


@dataclass
class AmbienceAction:
    """Control ambience."""
    filename: Optional[str] = None  # None means stop
    options: AmbienceOptions = field(default_factory=AmbienceOptions)


@dataclass
class GagAction:
    """Gag/suppress the matched line."""
    pass


@dataclass
class HighlightAction:
    """Highlight the matched text."""
    color: str


@dataclass
class VarAction:
    """Set a variable."""
    name: str
    expression: Expression


@dataclass
class IfAction:
    """Conditional action."""
    condition: Condition
    then_actions: list
    else_actions: list = field(default_factory=list)


Action = Union[SendAction, SoundAction, SoundStopAction, AmbienceAction, GagAction,
               HighlightAction, VarAction, IfAction]


# Statement types
@dataclass
class Trigger:
    """A trigger definition."""
    pattern: Pattern
    actions: list[Action]


@dataclass
class Gag:
    """A gag definition."""
    pattern: Pattern


@dataclass
class Alias:
    """An alias definition."""
    shortcut: str
    expansion: str


@dataclass
class SoundTrigger:
    """A sound trigger (shorthand for trigger + sound)."""
    pattern: Pattern
    filename: str
    options: SoundOptions = field(default_factory=SoundOptions)


@dataclass
class Script:
    """A complete parsed script."""
    triggers: list[Trigger] = field(default_factory=list)
    gags: list[Gag] = field(default_factory=list)
    aliases: list[Alias] = field(default_factory=list)
    sound_triggers: list[SoundTrigger] = field(default_factory=list)
    variables: dict[str, str] = field(default_factory=dict)


class DSLTransformer(Transformer):
    """Transform parse tree into Script objects."""

    def statement(self, items):
        """Unwrap statement to its child."""
        return items[0] if items else None

    def action(self, items):
        """Unwrap action to its child."""
        return items[0] if items else None

    def start(self, items):
        script = Script()
        for item in items:
            if isinstance(item, Trigger):
                script.triggers.append(item)
            elif isinstance(item, Gag):
                script.gags.append(item)
            elif isinstance(item, Alias):
                script.aliases.append(item)
            elif isinstance(item, SoundTrigger):
                script.sound_triggers.append(item)
            elif isinstance(item, tuple) and item[0] == "var":
                script.variables[item[1]] = item[2]
        return script

    # Statements
    def trigger_stmt(self, items):
        pattern, actions = items
        return Trigger(pattern=pattern, actions=actions)

    def gag_stmt(self, items):
        return Gag(pattern=items[0])

    def alias_stmt(self, items):
        shortcut = self._unquote(items[0])
        expansion = self._unquote(items[1])
        return Alias(shortcut=shortcut, expansion=expansion)

    def sound_trigger_stmt(self, items):
        pattern = items[0]
        filename = self._unquote(items[1])
        options = items[2] if len(items) > 2 else SoundOptions()
        return SoundTrigger(pattern=pattern, filename=filename, options=options)

    def ambience_stmt(self, items):
        if items[0] == "stop":
            return ("ambience", None, AmbienceOptions())
        filename = self._unquote(items[0])
        options = items[1] if len(items) > 1 else AmbienceOptions()
        return ("ambience", filename, options)

    def variable_stmt(self, items):
        name = str(items[0])
        expr = items[1]
        # Evaluate simple string expressions
        if len(expr.parts) == 1 and expr.parts[0][0] == "string":
            return ("var", name, expr.parts[0][1])
        return ("var", name, "")

    # Patterns
    def literal_pattern(self, items):
        return Pattern(pattern=self._unquote(items[0]), is_regex=False)

    def regex_pattern(self, items):
        regex_str = str(items[0])
        # Parse /pattern/flags format
        case_insensitive = regex_str.endswith("i")
        if case_insensitive:
            regex_str = regex_str[:-1]
        # Remove leading and trailing slashes
        pattern = regex_str[1:-1]
        return Pattern(pattern=pattern, is_regex=True,
                      case_insensitive=case_insensitive)

    # Block and actions
    def block(self, items):
        return list(items)

    def send_action(self, items):
        return SendAction(expression=items[0])

    def sound_play(self, items):
        """Handle sound "file" [options] action."""
        filename = self._unquote(items[0])
        options = items[1] if len(items) > 1 else SoundOptions()
        return SoundAction(filename=filename, options=options)

    def sound_stop(self, items):
        """Handle sound stop [id] action."""
        sound_id = self._unquote(items[0]) if items else None
        return SoundStopAction(sound_id=sound_id)

    # Keep for backwards compatibility
    def sound_action(self, items):
        filename = self._unquote(items[0])
        options = items[1] if len(items) > 1 else SoundOptions()
        return SoundAction(filename=filename, options=options)

    def ambience_play(self, items):
        """Handle ambience filename [options] action."""
        filename = self._unquote(items[0])
        options = items[1] if len(items) > 1 else AmbienceOptions()
        return AmbienceAction(filename=filename, options=options)

    def ambience_stop(self, items):
        """Handle ambience stop action."""
        return AmbienceAction(filename=None)

    # Keep for backwards compatibility
    def ambience_action(self, items):
        if items and items[0] == "stop":
            return AmbienceAction(filename=None)
        filename = self._unquote(items[0])
        options = items[1] if len(items) > 1 else AmbienceOptions()
        return AmbienceAction(filename=filename, options=options)

    def gag_action(self, items):
        return GagAction()

    def highlight_action(self, items):
        return HighlightAction(color=items[0])

    def var_action(self, items):
        name = str(items[0])
        return VarAction(name=name, expression=items[1])

    def if_action(self, items):
        condition = items[0]
        then_actions = items[1]
        else_actions = items[2] if len(items) > 2 else []
        return IfAction(condition=condition, then_actions=then_actions,
                       else_actions=else_actions)

    # Sound options
    def sound_options(self, items):
        opts = SoundOptions()
        for item in items:
            if item[0] == "volume":
                opts.volume = item[1]
            elif item[0] == "loop":
                opts.loops = item[1]
            elif item[0] == "priority":
                opts.priority = item[1]
            elif item[0] == "id":
                opts.id = item[1]
        return opts

    def opt_volume(self, items):
        return ("volume", int(items[0]))

    def opt_loop(self, items):
        if not items:
            # "infinite" is a terminal, not captured in items
            return ("loop", -1)
        val = str(items[0])
        if val == "infinite":
            return ("loop", -1)
        return ("loop", int(val))

    def opt_priority(self, items):
        return ("priority", int(items[0]))

    def opt_id(self, items):
        return ("id", self._unquote(items[0]))

    # Ambience options
    def ambience_options(self, items):
        opts = AmbienceOptions()
        for item in items:
            if item[0] == "loop":
                opts.loop = True
            elif item[0] == "volume":
                opts.volume = item[1]
            elif item[0] == "fadein":
                opts.fadein = item[1]
        return opts

    def opt_amb_loop(self, items):
        return ("loop", True)

    def opt_amb_volume(self, items):
        return ("volume", int(items[0]))

    def opt_amb_fadein(self, items):
        return ("fadein", int(items[0]))

    # Colors
    def named_color(self, items):
        return str(items[0])

    def hex_color(self, items):
        return f"#{items[0]}"

    # Conditions
    def var_condition(self, items):
        name = str(items[0])
        op = items[1]
        right = self._eval_expression(items[2])
        return Condition(left_var=name, op=op, right=right)

    def match_condition(self, items):
        group = int(items[0])
        op = items[1]
        right = self._eval_expression(items[2])
        return Condition(match_group=group, op=op, right=right)

    # Comparison operators
    def eq(self, items): return ComparisonOp.EQ
    def ne(self, items): return ComparisonOp.NE
    def gt(self, items): return ComparisonOp.GT
    def lt(self, items): return ComparisonOp.LT
    def ge(self, items): return ComparisonOp.GE
    def le(self, items): return ComparisonOp.LE

    # Expressions
    def expression(self, items):
        return Expression(parts=list(items))

    def string_val(self, items):
        return ("string", self._unquote(items[0]))

    def number_val(self, items):
        return ("number", str(items[0]))

    def var_val(self, items):
        return ("var", str(items[0]))

    def match_val(self, items):
        return ("match", int(items[0]))

    # Helpers
    def _unquote(self, s):
        """Remove quotes from string and handle escapes."""
        s = str(s)
        if s.startswith('"') and s.endswith('"'):
            s = s[1:-1]
        # Handle escape sequences
        s = s.replace('\\"', '"')
        s = s.replace('\\n', '\n')
        s = s.replace('\\t', '\t')
        s = s.replace('\\\\', '\\')
        return s

    def _eval_expression(self, expr):
        """Simple expression evaluation for conditions."""
        if isinstance(expr, Expression):
            parts = []
            for part_type, part_val in expr.parts:
                if part_type == "string":
                    parts.append(part_val)
                elif part_type == "number":
                    parts.append(part_val)
            return "".join(parts)
        return str(expr)


class DSLParser:
    """Parser for the GTK MUD DSL."""

    def __init__(self):
        with open(GRAMMAR_PATH) as f:
            grammar = f.read()
        self._parser = Lark(grammar, start='start', parser='lalr')
        self._transformer = DSLTransformer()

    def parse(self, script: str) -> Script:
        """Parse a script string.

        Args:
            script: The DSL script text.

        Returns:
            Parsed Script object.

        Raises:
            lark.exceptions.LarkError: If parsing fails.
        """
        tree = self._parser.parse(script)
        return self._transformer.transform(tree)

    def parse_file(self, path: Path) -> Script:
        """Parse a script file.

        Args:
            path: Path to the script file.

        Returns:
            Parsed Script object.
        """
        with open(path) as f:
            content = f.read()
        return self.parse(content)
