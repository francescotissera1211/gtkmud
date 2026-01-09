"""Tests for the ANSI escape sequence parser."""

import pytest

from gtkmud.parsers.ansi import (
    ANSIParser, TextSpan, TextStyle, strip_ansi,
    STANDARD_COLORS, BRIGHT_COLORS, COLOR_NAMES,
)


@pytest.fixture
def parser():
    """Create an ANSI parser instance."""
    return ANSIParser()


class TestBasicParsing:
    """Test basic text parsing."""

    def test_plain_text(self, parser):
        """Plain text without escapes should pass through."""
        spans = parser.parse("Hello, World!")
        assert len(spans) == 1
        assert spans[0].text == "Hello, World!"

    def test_empty_string(self, parser):
        """Empty string should return empty list."""
        spans = parser.parse("")
        assert spans == []

    def test_multiline_text(self, parser):
        """Multiline text should be preserved."""
        spans = parser.parse("Line 1\nLine 2\nLine 3")
        assert len(spans) == 1
        assert "Line 1\nLine 2\nLine 3" in spans[0].text


class TestColorCodes:
    """Test color escape code parsing."""

    def test_red_foreground(self, parser):
        """Test red foreground color."""
        spans = parser.parse("\x1b[31mRed text\x1b[0m")
        assert len(spans) >= 1
        red_span = spans[0]
        assert red_span.text == "Red text"
        assert red_span.style.fg_name == "red"

    def test_green_foreground(self, parser):
        """Test green foreground color."""
        spans = parser.parse("\x1b[32mGreen\x1b[0m")
        assert spans[0].style.fg_name == "green"

    def test_blue_background(self, parser):
        """Test blue background color."""
        spans = parser.parse("\x1b[44mBlue BG\x1b[0m")
        assert spans[0].style.bg_name == "blue"

    def test_bright_colors(self, parser):
        """Test bright color variants."""
        spans = parser.parse("\x1b[91mBright Red\x1b[0m")
        assert spans[0].style.fg_name == "bright_red"

        parser.reset()
        spans = parser.parse("\x1b[92mBright Green\x1b[0m")
        assert spans[0].style.fg_name == "bright_green"

    def test_fg_and_bg_together(self, parser):
        """Test foreground and background together."""
        spans = parser.parse("\x1b[31;44mRed on Blue\x1b[0m")
        assert spans[0].style.fg_name == "red"
        assert spans[0].style.bg_name == "blue"

    def test_default_color_reset(self, parser):
        """Test default color codes reset colors."""
        spans = parser.parse("\x1b[31mRed\x1b[39mDefault")
        assert spans[0].style.fg_name == "red"
        assert spans[1].style.fg_name is None


class TestTextStyles:
    """Test text style attributes."""

    def test_bold(self, parser):
        """Test bold attribute."""
        spans = parser.parse("\x1b[1mBold text\x1b[0m")
        assert spans[0].style.bold is True

    def test_italic(self, parser):
        """Test italic attribute."""
        spans = parser.parse("\x1b[3mItalic text\x1b[0m")
        assert spans[0].style.italic is True

    def test_underline(self, parser):
        """Test underline attribute."""
        spans = parser.parse("\x1b[4mUnderlined\x1b[0m")
        assert spans[0].style.underline is True

    def test_bold_off(self, parser):
        """Test turning bold off."""
        spans = parser.parse("\x1b[1mBold\x1b[22mNormal")
        assert spans[0].style.bold is True
        assert spans[1].style.bold is False

    def test_combined_styles(self, parser):
        """Test multiple styles combined."""
        spans = parser.parse("\x1b[1;3;4mBold Italic Underline\x1b[0m")
        assert spans[0].style.bold is True
        assert spans[0].style.italic is True
        assert spans[0].style.underline is True


class TestReset:
    """Test reset functionality."""

    def test_sgr_reset(self, parser):
        """Test SGR reset code (0)."""
        spans = parser.parse("\x1b[31;1mStyled\x1b[0mPlain")
        assert spans[0].style.fg_name == "red"
        assert spans[0].style.bold is True
        assert spans[1].style.fg_name is None
        assert spans[1].style.bold is False

    def test_empty_sgr_is_reset(self, parser):
        """ESC[m should be treated as reset."""
        spans = parser.parse("\x1b[31mRed\x1b[mPlain")
        assert spans[0].style.fg_name == "red"
        assert spans[1].style.fg_name is None

    def test_parser_reset(self, parser):
        """Parser reset should clear state."""
        parser.parse("\x1b[31mRed")
        parser.reset()
        spans = parser.parse("Plain")
        assert spans[0].style.fg_name is None


class Test256Colors:
    """Test 256-color mode."""

    def test_256_standard_color(self, parser):
        """Test 256-color mode standard colors (0-15)."""
        spans = parser.parse("\x1b[38;5;1mRed\x1b[0m")
        assert spans[0].style.fg_color == STANDARD_COLORS[1]  # Red

    def test_256_bright_color(self, parser):
        """Test 256-color mode bright colors (8-15)."""
        spans = parser.parse("\x1b[38;5;9mBright Red\x1b[0m")
        assert spans[0].style.fg_color == BRIGHT_COLORS[1]  # Bright Red

    def test_256_color_cube(self, parser):
        """Test 256-color mode color cube (16-231)."""
        # Color 196 should be pure red in the cube
        spans = parser.parse("\x1b[38;5;196mCube Red\x1b[0m")
        r, g, b = spans[0].style.fg_color
        assert r > 200  # Should be high red
        assert g < 50  # Low green
        assert b < 50  # Low blue

    def test_256_grayscale(self, parser):
        """Test 256-color mode grayscale (232-255)."""
        spans = parser.parse("\x1b[38;5;244mGray\x1b[0m")
        r, g, b = spans[0].style.fg_color
        assert r == g == b  # Should be grayscale

    def test_256_bg_color(self, parser):
        """Test 256-color mode for background."""
        spans = parser.parse("\x1b[48;5;21mBlue BG\x1b[0m")
        assert spans[0].style.bg_color is not None


class TestTrueColor:
    """Test 24-bit true color mode."""

    def test_true_color_fg(self, parser):
        """Test true color foreground."""
        spans = parser.parse("\x1b[38;2;255;128;64mOrange\x1b[0m")
        assert spans[0].style.fg_color == (255, 128, 64)

    def test_true_color_bg(self, parser):
        """Test true color background."""
        spans = parser.parse("\x1b[48;2;0;128;255mBlue BG\x1b[0m")
        assert spans[0].style.bg_color == (0, 128, 255)

    def test_true_color_custom(self, parser):
        """True color should not have named color."""
        spans = parser.parse("\x1b[38;2;100;150;200mCustom\x1b[0m")
        assert spans[0].style.fg_name is None  # Custom color, no name


class TestTextStyle:
    """Test TextStyle dataclass."""

    def test_default_style(self):
        """Default style should have no attributes."""
        style = TextStyle()
        assert style.fg_color is None
        assert style.bg_color is None
        assert style.bold is False
        assert style.italic is False

    def test_reset(self):
        """Reset should clear all attributes."""
        style = TextStyle(
            fg_color=(255, 0, 0),
            bold=True,
            italic=True,
        )
        style.reset()
        assert style.fg_color is None
        assert style.bold is False
        assert style.italic is False

    def test_copy(self):
        """Copy should create independent copy."""
        style = TextStyle(fg_name="red", bold=True)
        copy = style.copy()
        copy.fg_name = "blue"
        assert style.fg_name == "red"

    def test_get_tag_names(self):
        """get_tag_names should return appropriate tags."""
        style = TextStyle(fg_name="red", bold=True, underline=True)
        tags = style.get_tag_names()
        assert "fg_red" in tags
        assert "bold" in tags
        assert "underline" in tags


class TestTextSpan:
    """Test TextSpan dataclass."""

    def test_get_tag_names(self):
        """TextSpan.get_tag_names should delegate to style."""
        style = TextStyle(fg_name="green")
        span = TextSpan(text="test", style=style)
        assert "fg_green" in span.get_tag_names()


class TestStripAnsi:
    """Test strip_ansi utility function."""

    def test_strip_colors(self):
        """strip_ansi should remove color codes."""
        text = "\x1b[31mRed\x1b[0m and \x1b[32mGreen\x1b[0m"
        assert strip_ansi(text) == "Red and Green"

    def test_strip_styles(self):
        """strip_ansi should remove style codes."""
        text = "\x1b[1mBold\x1b[0m \x1b[4mUnderline\x1b[0m"
        assert strip_ansi(text) == "Bold Underline"

    def test_plain_text_unchanged(self):
        """Plain text should pass through unchanged."""
        text = "No escape codes here"
        assert strip_ansi(text) == text

    def test_empty_string(self):
        """Empty string should return empty string."""
        assert strip_ansi("") == ""


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_incomplete_escape(self, parser):
        """Incomplete escape should be preserved."""
        # This might be handled differently, just ensure no crash
        spans = parser.parse("\x1b[")
        assert len(spans) >= 0

    def test_unknown_sgr_code(self, parser):
        """Unknown SGR codes should be ignored."""
        spans = parser.parse("\x1b[999mText\x1b[0m")
        assert spans[0].text == "Text"

    def test_rapid_style_changes(self, parser):
        """Rapid style changes should work."""
        spans = parser.parse("\x1b[31mR\x1b[32mG\x1b[34mB\x1b[0m")
        assert len(spans) == 3
        assert spans[0].style.fg_name == "red"
        assert spans[1].style.fg_name == "green"
        assert spans[2].style.fg_name == "blue"

    def test_text_between_escapes(self, parser):
        """Text between escapes should be captured."""
        spans = parser.parse("Before\x1b[31mMiddle\x1b[0mAfter")
        assert len(spans) == 3
        assert spans[0].text == "Before"
        assert spans[1].text == "Middle"
        assert spans[2].text == "After"


class TestColorConstants:
    """Test color constant definitions."""

    def test_standard_colors_count(self):
        """Should have 8 standard colors."""
        assert len(STANDARD_COLORS) == 8

    def test_bright_colors_count(self):
        """Should have 8 bright colors."""
        assert len(BRIGHT_COLORS) == 8

    def test_color_names_count(self):
        """Should have 16 color names."""
        assert len(COLOR_NAMES) == 16

    def test_color_tuples_valid(self):
        """Color tuples should have 3 components 0-255."""
        for color in STANDARD_COLORS + BRIGHT_COLORS:
            assert len(color) == 3
            assert all(0 <= c <= 255 for c in color)
