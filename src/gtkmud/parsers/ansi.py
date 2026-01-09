"""ANSI escape sequence parser for terminal colors and styles."""

import re
from dataclasses import dataclass, field
from typing import Optional
from enum import IntEnum


class SGR(IntEnum):
    """SGR (Select Graphic Rendition) codes."""
    RESET = 0
    BOLD = 1
    DIM = 2
    ITALIC = 3
    UNDERLINE = 4
    BLINK = 5
    BLINK_RAPID = 6
    REVERSE = 7
    HIDDEN = 8
    STRIKETHROUGH = 9

    BOLD_OFF = 21
    NORMAL_INTENSITY = 22
    ITALIC_OFF = 23
    UNDERLINE_OFF = 24
    BLINK_OFF = 25
    REVERSE_OFF = 27
    HIDDEN_OFF = 28
    STRIKETHROUGH_OFF = 29

    FG_BLACK = 30
    FG_RED = 31
    FG_GREEN = 32
    FG_YELLOW = 33
    FG_BLUE = 34
    FG_MAGENTA = 35
    FG_CYAN = 36
    FG_WHITE = 37
    FG_EXTENDED = 38
    FG_DEFAULT = 39

    BG_BLACK = 40
    BG_RED = 41
    BG_GREEN = 42
    BG_YELLOW = 43
    BG_BLUE = 44
    BG_MAGENTA = 45
    BG_CYAN = 46
    BG_WHITE = 47
    BG_EXTENDED = 48
    BG_DEFAULT = 49

    FG_BRIGHT_BLACK = 90
    FG_BRIGHT_RED = 91
    FG_BRIGHT_GREEN = 92
    FG_BRIGHT_YELLOW = 93
    FG_BRIGHT_BLUE = 94
    FG_BRIGHT_MAGENTA = 95
    FG_BRIGHT_CYAN = 96
    FG_BRIGHT_WHITE = 97

    BG_BRIGHT_BLACK = 100
    BG_BRIGHT_RED = 101
    BG_BRIGHT_GREEN = 102
    BG_BRIGHT_YELLOW = 103
    BG_BRIGHT_BLUE = 104
    BG_BRIGHT_MAGENTA = 105
    BG_BRIGHT_CYAN = 106
    BG_BRIGHT_WHITE = 107


# Standard ANSI colors (indices 0-7)
STANDARD_COLORS = [
    (0, 0, 0),        # Black
    (170, 0, 0),      # Red
    (0, 170, 0),      # Green
    (170, 85, 0),     # Yellow/Brown
    (0, 0, 170),      # Blue
    (170, 0, 170),    # Magenta
    (0, 170, 170),    # Cyan
    (170, 170, 170),  # White
]

# Bright ANSI colors (indices 8-15)
BRIGHT_COLORS = [
    (85, 85, 85),     # Bright Black (Gray)
    (255, 85, 85),    # Bright Red
    (85, 255, 85),    # Bright Green
    (255, 255, 85),   # Bright Yellow
    (85, 85, 255),    # Bright Blue
    (255, 85, 255),   # Bright Magenta
    (85, 255, 255),   # Bright Cyan
    (255, 255, 255),  # Bright White
]

# Color names for GTK tags
COLOR_NAMES = [
    "black", "red", "green", "yellow", "blue", "magenta", "cyan", "white",
    "bright_black", "bright_red", "bright_green", "bright_yellow",
    "bright_blue", "bright_magenta", "bright_cyan", "bright_white",
]


@dataclass
class TextStyle:
    """Current text style state."""
    fg_color: Optional[tuple[int, int, int]] = None
    bg_color: Optional[tuple[int, int, int]] = None
    fg_name: Optional[str] = None  # Tag name for standard colors
    bg_name: Optional[str] = None
    bold: bool = False
    dim: bool = False
    italic: bool = False
    underline: bool = False
    blink: bool = False
    reverse: bool = False

    def reset(self):
        """Reset all attributes to default."""
        self.fg_color = None
        self.bg_color = None
        self.fg_name = None
        self.bg_name = None
        self.bold = False
        self.dim = False
        self.italic = False
        self.underline = False
        self.blink = False
        self.reverse = False

    def get_tag_names(self) -> list[str]:
        """Get list of GTK text tag names for current style."""
        tags = []

        if self.fg_name:
            tags.append(f"fg_{self.fg_name}")
        if self.bg_name:
            tags.append(f"bg_{self.bg_name}")
        if self.bold:
            tags.append("bold")
        if self.italic:
            tags.append("italic")
        if self.underline:
            tags.append("underline")

        return tags

    def copy(self) -> "TextStyle":
        """Create a copy of this style."""
        return TextStyle(
            fg_color=self.fg_color,
            bg_color=self.bg_color,
            fg_name=self.fg_name,
            bg_name=self.bg_name,
            bold=self.bold,
            dim=self.dim,
            italic=self.italic,
            underline=self.underline,
            blink=self.blink,
            reverse=self.reverse,
        )


@dataclass
class TextSpan:
    """A span of text with associated style."""
    text: str
    style: TextStyle = field(default_factory=TextStyle)

    def get_tag_names(self) -> list[str]:
        """Get GTK tag names for this span."""
        return self.style.get_tag_names()


class ANSIParser:
    """Parser for ANSI escape sequences.

    Converts text with ANSI escape codes into a list of styled text spans
    suitable for rendering in a GTK text view.
    """

    # Pattern to match ANSI CSI sequences
    # Matches: ESC [ <params> <final byte>
    CSI_PATTERN = re.compile(r'\x1b\[([0-9;]*)([A-Za-z])')

    def __init__(self):
        self._style = TextStyle()

    def parse(self, text: str) -> list[TextSpan]:
        """Parse text with ANSI escape sequences.

        Args:
            text: Input text potentially containing ANSI sequences.

        Returns:
            List of TextSpan objects with plain text and styles.
        """
        spans = []
        pos = 0

        for match in self.CSI_PATTERN.finditer(text):
            # Add text before this escape sequence
            if match.start() > pos:
                plain_text = text[pos:match.start()]
                if plain_text:
                    spans.append(TextSpan(plain_text, self._style.copy()))

            # Process the escape sequence
            params = match.group(1)
            command = match.group(2)

            if command == 'm':  # SGR - Select Graphic Rendition
                self._process_sgr(params)

            pos = match.end()

        # Add remaining text
        if pos < len(text):
            remaining = text[pos:]
            if remaining:
                spans.append(TextSpan(remaining, self._style.copy()))

        return spans

    def _process_sgr(self, params: str):
        """Process SGR (Select Graphic Rendition) parameters."""
        if not params:
            # ESC[m is equivalent to ESC[0m
            self._style.reset()
            return

        codes = [int(c) if c else 0 for c in params.split(';')]
        i = 0

        while i < len(codes):
            code = codes[i]

            if code == SGR.RESET:
                self._style.reset()

            elif code == SGR.BOLD:
                self._style.bold = True
            elif code == SGR.DIM:
                self._style.dim = True
            elif code == SGR.ITALIC:
                self._style.italic = True
            elif code == SGR.UNDERLINE:
                self._style.underline = True
            elif code == SGR.BLINK or code == SGR.BLINK_RAPID:
                self._style.blink = True
            elif code == SGR.REVERSE:
                self._style.reverse = True

            elif code == SGR.BOLD_OFF or code == SGR.NORMAL_INTENSITY:
                self._style.bold = False
                self._style.dim = False
            elif code == SGR.ITALIC_OFF:
                self._style.italic = False
            elif code == SGR.UNDERLINE_OFF:
                self._style.underline = False
            elif code == SGR.BLINK_OFF:
                self._style.blink = False
            elif code == SGR.REVERSE_OFF:
                self._style.reverse = False

            # Standard foreground colors (30-37)
            elif 30 <= code <= 37:
                color_idx = code - 30
                self._style.fg_color = STANDARD_COLORS[color_idx]
                self._style.fg_name = COLOR_NAMES[color_idx]

            # Standard background colors (40-47)
            elif 40 <= code <= 47:
                color_idx = code - 40
                self._style.bg_color = STANDARD_COLORS[color_idx]
                self._style.bg_name = COLOR_NAMES[color_idx]

            # Bright foreground colors (90-97)
            elif 90 <= code <= 97:
                color_idx = code - 90
                self._style.fg_color = BRIGHT_COLORS[color_idx]
                self._style.fg_name = COLOR_NAMES[color_idx + 8]

            # Bright background colors (100-107)
            elif 100 <= code <= 107:
                color_idx = code - 100
                self._style.bg_color = BRIGHT_COLORS[color_idx]
                self._style.bg_name = COLOR_NAMES[color_idx + 8]

            # Extended foreground color (38;5;n or 38;2;r;g;b)
            elif code == SGR.FG_EXTENDED:
                if i + 1 < len(codes):
                    mode = codes[i + 1]
                    if mode == 5 and i + 2 < len(codes):
                        # 256-color mode
                        color = self._get_256_color(codes[i + 2])
                        self._style.fg_color = color
                        self._style.fg_name = None  # Custom color
                        i += 2
                    elif mode == 2 and i + 4 < len(codes):
                        # True color mode
                        r, g, b = codes[i + 2], codes[i + 3], codes[i + 4]
                        self._style.fg_color = (r, g, b)
                        self._style.fg_name = None
                        i += 4

            # Extended background color (48;5;n or 48;2;r;g;b)
            elif code == SGR.BG_EXTENDED:
                if i + 1 < len(codes):
                    mode = codes[i + 1]
                    if mode == 5 and i + 2 < len(codes):
                        # 256-color mode
                        color = self._get_256_color(codes[i + 2])
                        self._style.bg_color = color
                        self._style.bg_name = None
                        i += 2
                    elif mode == 2 and i + 4 < len(codes):
                        # True color mode
                        r, g, b = codes[i + 2], codes[i + 3], codes[i + 4]
                        self._style.bg_color = (r, g, b)
                        self._style.bg_name = None
                        i += 4

            # Default colors
            elif code == SGR.FG_DEFAULT:
                self._style.fg_color = None
                self._style.fg_name = None
            elif code == SGR.BG_DEFAULT:
                self._style.bg_color = None
                self._style.bg_name = None

            i += 1

    def _get_256_color(self, n: int) -> tuple[int, int, int]:
        """Convert 256-color palette index to RGB."""
        if n < 0 or n > 255:
            return (255, 255, 255)

        # Colors 0-15: Standard and bright colors
        if n < 16:
            if n < 8:
                return STANDARD_COLORS[n]
            else:
                return BRIGHT_COLORS[n - 8]

        # Colors 16-231: 6x6x6 color cube
        if n < 232:
            n -= 16
            r = (n // 36) % 6
            g = (n // 6) % 6
            b = n % 6
            # Map 0-5 to 0, 95, 135, 175, 215, 255
            r = 0 if r == 0 else 55 + r * 40
            g = 0 if g == 0 else 55 + g * 40
            b = 0 if b == 0 else 55 + b * 40
            return (r, g, b)

        # Colors 232-255: Grayscale
        gray = 8 + (n - 232) * 10
        return (gray, gray, gray)

    def reset(self):
        """Reset parser state."""
        self._style.reset()


def strip_ansi(text: str) -> str:
    """Remove all ANSI escape sequences from text.

    Args:
        text: Input text with ANSI sequences.

    Returns:
        Plain text with sequences removed.
    """
    return ANSIParser.CSI_PATTERN.sub('', text)
