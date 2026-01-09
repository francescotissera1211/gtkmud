"""Script interpreter for executing triggers, gags, and aliases."""

import re
import logging
from typing import Optional, Callable
from dataclasses import dataclass

from gtkmud.scripting.parser import (
    Script, Trigger, Gag, Alias, SoundTrigger, Pattern,
    Action, SendAction, SoundAction, SoundStopAction, AmbienceAction,
    GagAction, HighlightAction, VarAction, IfAction,
    Expression, Condition, ComparisonOp,
)

logger = logging.getLogger(__name__)


@dataclass
class TriggerResult:
    """Result of processing a trigger."""
    should_gag: bool = False
    highlight_color: Optional[str] = None
    commands_to_send: list[str] = None
    sounds_to_play: list[tuple] = None  # (filename, options)
    sounds_to_stop: list[Optional[str]] = None  # list of IDs to stop, None = stop all
    ambience: Optional[tuple] = None  # (filename, options) or (None,) for stop

    def __post_init__(self):
        if self.commands_to_send is None:
            self.commands_to_send = []
        if self.sounds_to_play is None:
            self.sounds_to_play = []
        if self.sounds_to_stop is None:
            self.sounds_to_stop = []


class ScriptInterpreter:
    """Interprets and executes DSL scripts.

    Provides:
    - Trigger matching and action execution
    - Gag checking
    - Alias expansion
    - Variable management
    """

    def __init__(self, script: Optional[Script] = None):
        """Initialize interpreter with optional script.

        Args:
            script: Parsed Script object to execute.
        """
        self._script = script or Script()
        self._variables: dict[str, str] = {}
        self._current_match: Optional[re.Match] = None

        # Callbacks for actions
        self.on_send: Optional[Callable[[str], None]] = None
        self.on_sound: Optional[Callable[[str, dict], None]] = None
        self.on_sound_stop: Optional[Callable[[Optional[str]], None]] = None  # None = stop all
        self.on_ambience: Optional[Callable[[Optional[str], dict], None]] = None

        # Initialize variables from script
        if script:
            self._variables.update(script.variables)

    def set_script(self, script: Script):
        """Set the script to execute.

        Args:
            script: Parsed Script object.
        """
        self._script = script
        self._variables.update(script.variables)

    def check_gag(self, line: str) -> bool:
        """Check if a line should be gagged (suppressed).

        Args:
            line: The line of text to check.

        Returns:
            True if the line should be gagged.
        """
        for gag in self._script.gags:
            if gag.pattern.match(line):
                logger.debug(f"Line gagged by pattern: {gag.pattern.pattern}")
                return True
        return False

    def expand_alias(self, command: str) -> str:
        """Expand aliases in a command.

        Args:
            command: The user's input command.

        Returns:
            Command with aliases expanded.
        """
        # Check for exact match first
        for alias in self._script.aliases:
            if command == alias.shortcut:
                return alias.expansion

        # Check for prefix match (alias followed by space and args)
        for alias in self._script.aliases:
            if command.startswith(alias.shortcut + " "):
                rest = command[len(alias.shortcut) + 1:]
                return f"{alias.expansion} {rest}"

        return command

    def process_line(self, line: str) -> TriggerResult:
        """Process a line through all triggers.

        Args:
            line: The line of text from the server.

        Returns:
            TriggerResult with all accumulated actions.
        """
        result = TriggerResult()

        # Check regular triggers
        for trigger in self._script.triggers:
            match = trigger.pattern.match(line)
            if match:
                self._current_match = match
                self._execute_actions(trigger.actions, result)
                self._current_match = None

        # Check sound triggers
        for sound_trigger in self._script.sound_triggers:
            if sound_trigger.pattern.match(line):
                result.sounds_to_play.append(
                    (sound_trigger.filename, {
                        "volume": sound_trigger.options.volume,
                        "loops": sound_trigger.options.loops,
                        "priority": sound_trigger.options.priority,
                    })
                )

        return result

    def _execute_actions(self, actions: list[Action], result: TriggerResult):
        """Execute a list of actions, accumulating results.

        Args:
            actions: List of actions to execute.
            result: TriggerResult to accumulate into.
        """
        for action in actions:
            if isinstance(action, SendAction):
                cmd = self._eval_expression(action.expression)
                result.commands_to_send.append(cmd)
                if self.on_send:
                    self.on_send(cmd)

            elif isinstance(action, SoundAction):
                options = {
                    "volume": action.options.volume,
                    "loops": action.options.loops,
                    "priority": action.options.priority,
                }
                if action.options.id:
                    options["id"] = action.options.id
                result.sounds_to_play.append((action.filename, options))
                if self.on_sound:
                    self.on_sound(action.filename, options)

            elif isinstance(action, SoundStopAction):
                result.sounds_to_stop.append(action.sound_id)
                if self.on_sound_stop:
                    self.on_sound_stop(action.sound_id)

            elif isinstance(action, AmbienceAction):
                if action.filename is None:
                    result.ambience = (None, {})
                    if self.on_ambience:
                        self.on_ambience(None, {})
                else:
                    opts = {
                        "volume": action.options.volume,
                        "fadein": action.options.fadein,
                    }
                    result.ambience = (action.filename, opts)
                    if self.on_ambience:
                        self.on_ambience(action.filename, opts)

            elif isinstance(action, GagAction):
                result.should_gag = True

            elif isinstance(action, HighlightAction):
                result.highlight_color = action.color

            elif isinstance(action, VarAction):
                value = self._eval_expression(action.expression)
                self._variables[action.name] = value

            elif isinstance(action, IfAction):
                if self._eval_condition(action.condition):
                    self._execute_actions(action.then_actions, result)
                elif action.else_actions:
                    self._execute_actions(action.else_actions, result)

    def _eval_expression(self, expr: Expression) -> str:
        """Evaluate an expression to a string.

        Args:
            expr: The expression to evaluate.

        Returns:
            String result.
        """
        parts = []
        for part_type, part_val in expr.parts:
            if part_type == "string":
                parts.append(part_val)
            elif part_type == "number":
                parts.append(str(part_val))
            elif part_type == "var":
                parts.append(self._variables.get(part_val, ""))
            elif part_type == "match":
                if self._current_match:
                    try:
                        parts.append(self._current_match.group(part_val))
                    except IndexError:
                        parts.append("")
                else:
                    parts.append("")
        return "".join(parts)

    def _eval_condition(self, cond: Condition) -> bool:
        """Evaluate a condition.

        Args:
            cond: The condition to evaluate.

        Returns:
            Boolean result.
        """
        # Get left value
        if cond.left_var:
            left = self._variables.get(cond.left_var, "")
        elif cond.match_group is not None and self._current_match:
            try:
                left = self._current_match.group(cond.match_group)
            except IndexError:
                left = ""
        else:
            left = ""

        right = cond.right

        # Compare
        if cond.op == ComparisonOp.EQ:
            return left == right
        elif cond.op == ComparisonOp.NE:
            return left != right
        elif cond.op == ComparisonOp.GT:
            try:
                return float(left) > float(right)
            except ValueError:
                return left > right
        elif cond.op == ComparisonOp.LT:
            try:
                return float(left) < float(right)
            except ValueError:
                return left < right
        elif cond.op == ComparisonOp.GE:
            try:
                return float(left) >= float(right)
            except ValueError:
                return left >= right
        elif cond.op == ComparisonOp.LE:
            try:
                return float(left) <= float(right)
            except ValueError:
                return left <= right

        return False

    def get_variable(self, name: str) -> str:
        """Get a variable value.

        Args:
            name: Variable name.

        Returns:
            Variable value or empty string.
        """
        return self._variables.get(name, "")

    def set_variable(self, name: str, value: str):
        """Set a variable value.

        Args:
            name: Variable name.
            value: Variable value.
        """
        self._variables[name] = value

    @property
    def triggers(self) -> list[Trigger]:
        """Get list of triggers."""
        return self._script.triggers

    @property
    def gags(self) -> list[Gag]:
        """Get list of gags."""
        return self._script.gags

    @property
    def aliases(self) -> list[Alias]:
        """Get list of aliases."""
        return self._script.aliases

    @property
    def variables(self) -> dict[str, str]:
        """Get all variables."""
        return dict(self._variables)
