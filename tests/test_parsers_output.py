"""Tests for the output parser module."""

import pytest

from mother.parsers.output import (
    ANSI_PATTERN,
    BOX_CHARS,
    OutputParser,
    TableParseResult,
    strip_ansi,
)


class TestStripAnsi:
    """Tests for strip_ansi function."""

    def test_removes_color_codes(self):
        """Test removal of color escape codes."""
        colored = "\x1b[31mRed text\x1b[0m"
        assert strip_ansi(colored) == "Red text"

    def test_removes_bold_codes(self):
        """Test removal of bold escape codes."""
        bold = "\x1b[1mBold text\x1b[0m"
        assert strip_ansi(bold) == "Bold text"

    def test_removes_multiple_codes(self):
        """Test removal of multiple escape codes."""
        text = "\x1b[1m\x1b[34mBlue bold\x1b[0m normal"
        assert strip_ansi(text) == "Blue bold normal"

    def test_preserves_plain_text(self):
        """Test that plain text is preserved."""
        text = "Hello, World!"
        assert strip_ansi(text) == text

    def test_empty_string(self):
        """Test with empty string."""
        assert strip_ansi("") == ""

    def test_only_escape_codes(self):
        """Test string with only escape codes."""
        text = "\x1b[31m\x1b[0m"
        assert strip_ansi(text) == ""

    def test_cursor_movement_codes(self):
        """Test removal of cursor movement codes."""
        text = "\x1b[2J\x1b[HHello"  # Clear screen and home cursor
        assert strip_ansi(text) == "Hello"


class TestAnsiPattern:
    """Tests for the ANSI pattern regex."""

    def test_pattern_matches_color_codes(self):
        """Test pattern matches standard color codes."""
        assert ANSI_PATTERN.search("\x1b[31m")
        assert ANSI_PATTERN.search("\x1b[0m")
        assert ANSI_PATTERN.search("\x1b[1;34m")

    def test_pattern_matches_cursor_codes(self):
        """Test pattern matches cursor control codes."""
        assert ANSI_PATTERN.search("\x1b[2J")
        assert ANSI_PATTERN.search("\x1b[H")


class TestBoxChars:
    """Tests for BOX_CHARS constant."""

    def test_contains_common_box_chars(self):
        """Test BOX_CHARS contains common box drawing characters."""
        common = ["─", "│", "┌", "┐", "└", "┘", "├", "┤"]
        for char in common:
            assert char in BOX_CHARS

    def test_contains_heavy_box_chars(self):
        """Test BOX_CHARS contains heavy box drawing characters."""
        heavy = ["━", "┃", "┏", "┓", "┗", "┛"]
        for char in heavy:
            assert char in BOX_CHARS

    def test_contains_double_line_chars(self):
        """Test BOX_CHARS contains double-line box characters."""
        double = ["═", "║", "╔", "╗", "╚", "╝"]
        for char in double:
            assert char in BOX_CHARS


class TestTableParseResult:
    """Tests for TableParseResult dataclass."""

    def test_creation_with_defaults(self):
        """Test creation with default title."""
        result = TableParseResult(headers=["A", "B"], rows=[{"A": "1", "B": "2"}])
        assert result.headers == ["A", "B"]
        assert result.rows == [{"A": "1", "B": "2"}]
        assert result.title is None

    def test_creation_with_title(self):
        """Test creation with title."""
        result = TableParseResult(
            headers=["Name"],
            rows=[{"Name": "Test"}],
            title="My Table",
        )
        assert result.title == "My Table"

    def test_empty_table(self):
        """Test creation with empty rows."""
        result = TableParseResult(headers=["X"], rows=[])
        assert result.rows == []


class TestOutputParser:
    """Tests for OutputParser class."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return OutputParser()

    class TestIsSeparatorLine:
        """Tests for is_separator_line method."""

        @pytest.fixture
        def parser(self):
            return OutputParser()

        def test_horizontal_line_is_separator(self, parser):
            """Test horizontal line is recognized as separator."""
            assert parser.is_separator_line("─────────")
            assert parser.is_separator_line("━━━━━━━━━")
            assert parser.is_separator_line("═════════")

        def test_line_with_corners_is_separator(self, parser):
            """Test line with corners is recognized as separator."""
            assert parser.is_separator_line("┌─────────┐")
            assert parser.is_separator_line("└─────────┘")
            assert parser.is_separator_line("├─────────┤")

        def test_content_line_not_separator(self, parser):
            """Test content line is not recognized as separator."""
            assert not parser.is_separator_line("│ Hello │")
            assert not parser.is_separator_line("Hello World")

        def test_empty_line_not_separator(self, parser):
            """Test empty line is not separator."""
            assert not parser.is_separator_line("")
            assert not parser.is_separator_line("   ")

        def test_mixed_content_not_separator(self, parser):
            """Test mixed content is not separator."""
            assert not parser.is_separator_line("──Hello──")

        def test_ansi_codes_stripped(self, parser):
            """Test ANSI codes are stripped before checking."""
            assert parser.is_separator_line("\x1b[34m───────\x1b[0m")

    class TestGetCellSeparator:
        """Tests for get_cell_separator method."""

        @pytest.fixture
        def parser(self):
            return OutputParser()

        def test_finds_pipe_separator(self, parser):
            """Test finding pipe separator."""
            assert parser.get_cell_separator("│ A │ B │") == "│"

        def test_finds_heavy_pipe_separator(self, parser):
            """Test finding heavy pipe separator."""
            assert parser.get_cell_separator("┃ A ┃ B ┃") == "┃"

        def test_finds_double_pipe_separator(self, parser):
            """Test finding double pipe separator."""
            assert parser.get_cell_separator("║ A ║ B ║") == "║"

        def test_no_separator(self, parser):
            """Test when no separator is present."""
            assert parser.get_cell_separator("Hello World") is None

        def test_priority_order(self, parser):
            """Test separator priority order (┃ > │ > ║)."""
            # ┃ should be found first
            assert parser.get_cell_separator("┃│") == "┃"

    class TestParseTable:
        """Tests for parse_table method."""

        @pytest.fixture
        def parser(self):
            return OutputParser()

        def test_simple_table(self, parser):
            """Test parsing a simple table."""
            table = """
┌──────┬───────┐
│ Name │ Value │
├──────┼───────┤
│ foo  │ 123   │
├──────┼───────┤
│ bar  │ 456   │
└──────┴───────┘
"""
            result = parser.parse_table(table)
            assert result is not None
            assert result.headers == ["Name", "Value"]
            assert len(result.rows) == 2
            assert result.rows[0] == {"Name": "foo", "Value": "123"}
            assert result.rows[1] == {"Name": "bar", "Value": "456"}

        def test_table_with_title(self, parser):
            """Test parsing table with title."""
            table = """
My Data
┌──────┬───────┐
│ A    │ B     │
├──────┼───────┤
│ 1    │ 2     │
└──────┴───────┘
"""
            result = parser.parse_table(table)
            assert result is not None
            assert result.title == "My Data"

        def test_empty_table(self, parser):
            """Test parsing empty content."""
            result = parser.parse_table("")
            assert result is None

        def test_no_table_content(self, parser):
            """Test with non-table content."""
            result = parser.parse_table("Just some text without a table")
            assert result is None

        def test_table_with_ansi_codes(self, parser):
            """Test parsing table with ANSI color codes."""
            table = """
\x1b[34m┌──────┬───────┐\x1b[0m
\x1b[34m│\x1b[0m Name \x1b[34m│\x1b[0m Value \x1b[34m│\x1b[0m
\x1b[34m├──────┼───────┤\x1b[0m
\x1b[34m│\x1b[0m test \x1b[34m│\x1b[0m 42    \x1b[34m│\x1b[0m
\x1b[34m└──────┴───────┘\x1b[0m
"""
            result = parser.parse_table(table)
            assert result is not None
            assert "Name" in result.headers

    class TestParseMailcraftList:
        """Tests for parse_mailcraft_list method."""

        @pytest.fixture
        def parser(self):
            return OutputParser()

        def test_basic_email_list(self, parser):
            """Test parsing basic email list."""
            output = """
david@example.com - INBOX

┌───────┬──────────────────┬───────────────────────┬─────────────┐
│ ●     │ john@test.com    │ Meeting tomorrow      │ Dec 15      │
├───────┼──────────────────┼───────────────────────┼─────────────┤
│       │ jane@test.com    │ RE: Project update    │ Dec 14      │
└───────┴──────────────────┴───────────────────────┴─────────────┘
"""
            emails = parser.parse_mailcraft_list(output)
            assert len(emails) >= 1

        def test_empty_output(self, parser):
            """Test parsing empty output."""
            emails = parser.parse_mailcraft_list("")
            assert emails == []

        def test_no_emails(self, parser):
            """Test output with no emails."""
            output = "No messages found"
            emails = parser.parse_mailcraft_list(output)
            assert emails == []

    class TestExtractKeyValues:
        """Tests for extract_key_values method."""

        @pytest.fixture
        def parser(self):
            return OutputParser()

        def test_colon_separated(self, parser):
            """Test extracting colon-separated key-values."""
            output = """
Name: John Doe
Email: john@example.com
Status: Active
"""
            result = parser.extract_key_values(output)
            assert result["Name"] == "John Doe"
            assert result["Email"] == "john@example.com"
            assert result["Status"] == "Active"

        def test_space_separated(self, parser):
            """Test extracting space-separated key-values."""
            output = """
Name          John Doe
Count         42
"""
            result = parser.extract_key_values(output)
            assert result.get("Name") == "John Doe"
            assert result.get("Count") == "42"

        def test_with_ansi_codes(self, parser):
            """Test extraction with ANSI codes."""
            output = "\x1b[1mName:\x1b[0m Test Value"
            result = parser.extract_key_values(output)
            assert result.get("Name") == "Test Value"

        def test_empty_output(self, parser):
            """Test with empty output."""
            result = parser.extract_key_values("")
            assert result == {}

        def test_no_key_values(self, parser):
            """Test output without key-values."""
            result = parser.extract_key_values("Just some text")
            assert result == {}

    class TestExtractSummary:
        """Tests for extract_summary method."""

        @pytest.fixture
        def parser(self):
            return OutputParser()

        def test_message_count(self, parser):
            """Test extracting message count."""
            output = "Found 25 messages in your inbox"
            result = parser.extract_summary(output)
            assert result["messages"] == 25

        def test_multiple_counts(self, parser):
            """Test extracting multiple counts."""
            output = "10 new messages, 5 documents processed"
            result = parser.extract_summary(output)
            assert result["new"] == 10
            assert result["documents"] == 5

        def test_found_pattern(self, parser):
            """Test 'Found X' pattern."""
            output = "Found 42 results"
            result = parser.extract_summary(output)
            assert result["found"] == 42
            assert result["results"] == 42

        def test_total_pattern(self, parser):
            """Test 'Total: X' pattern."""
            output = "Total: 100"
            result = parser.extract_summary(output)
            assert result["total"] == 100

        def test_leads_pattern(self, parser):
            """Test leads count pattern."""
            output = "Processed 15 leads today"
            result = parser.extract_summary(output)
            assert result["leads"] == 15

        def test_accounts_pattern(self, parser):
            """Test accounts count pattern."""
            output = "3 accounts configured"
            result = parser.extract_summary(output)
            assert result["accounts"] == 3

        def test_case_insensitive(self, parser):
            """Test case insensitive matching."""
            output = "FOUND 50 RESULTS"
            result = parser.extract_summary(output)
            assert result["found"] == 50

        def test_empty_output(self, parser):
            """Test with empty output."""
            result = parser.extract_summary("")
            assert result == {}

    class TestExtractEmailHeader:
        """Tests for extract_email_header method."""

        @pytest.fixture
        def parser(self):
            return OutputParser()

        def test_full_header(self, parser):
            """Test extracting full email header."""
            output = """
From: sender@example.com
To: recipient@example.com
CC: cc@example.com
Date: Mon, 15 Dec 2025 10:30:00
Subject: Test Email
"""
            result = parser.extract_email_header(output)
            assert result["from"] == "sender@example.com"
            assert result["to"] == "recipient@example.com"
            assert result["cc"] == "cc@example.com"
            assert result["subject"] == "Test Email"
            assert "Dec" in result["date"]

        def test_partial_header(self, parser):
            """Test extracting partial header."""
            output = """
From: sender@example.com
Subject: Important
"""
            result = parser.extract_email_header(output)
            assert result["from"] == "sender@example.com"
            assert result["subject"] == "Important"
            assert "to" not in result

        def test_case_insensitive(self, parser):
            """Test case insensitive matching."""
            output = "FROM: test@test.com\nSUBJECT: Test"
            result = parser.extract_email_header(output)
            assert result["from"] == "test@test.com"
            assert result["subject"] == "Test"

        def test_empty_output(self, parser):
            """Test with empty output."""
            result = parser.extract_email_header("")
            assert result == {}

    class TestExtractBody:
        """Tests for extract_body method."""

        @pytest.fixture
        def parser(self):
            return OutputParser()

        def test_with_marker(self, parser):
            """Test extracting body after marker."""
            output = """
From: test@test.com
Subject: Test

Message ────────────────────
This is the body content.
It has multiple lines.
"""
            result = parser.extract_body(output, "Message")
            assert "body content" in result

        def test_fallback_after_blank(self, parser):
            """Test fallback extraction after blank line."""
            output = """
Header: Value

This is the body after blank line.
"""
            result = parser.extract_body(output, "NonExistent")
            assert "body after blank line" in result

        def test_custom_marker(self, parser):
            """Test with custom marker."""
            output = """
Content ═══════════════
Body text here
"""
            result = parser.extract_body(output, "Content")
            assert "Body text" in result

        def test_empty_output(self, parser):
            """Test with empty output."""
            result = parser.extract_body("", "Message")
            assert result == ""

    class TestIsSuccessMessage:
        """Tests for is_success_message method."""

        @pytest.fixture
        def parser(self):
            return OutputParser()

        def test_success_patterns(self, parser):
            """Test recognition of success patterns."""
            assert parser.is_success_message("Operation completed successfully")
            assert parser.is_success_message("Success: file saved")
            assert parser.is_success_message("Done processing")
            assert parser.is_success_message("Email sent!")
            assert parser.is_success_message("File created")
            assert parser.is_success_message("Changes saved")
            assert parser.is_success_message("Item moved")
            assert parser.is_success_message("Record deleted")

        def test_non_success_messages(self, parser):
            """Test non-success messages."""
            assert not parser.is_success_message("Processing...")
            assert not parser.is_success_message("Hello World")

        def test_case_insensitive(self, parser):
            """Test case insensitive matching."""
            assert parser.is_success_message("SUCCESS")
            assert parser.is_success_message("COMPLETED")

        def test_with_ansi_codes(self, parser):
            """Test with ANSI codes."""
            assert parser.is_success_message("\x1b[32mSuccess\x1b[0m")

    class TestIsErrorMessage:
        """Tests for is_error_message method."""

        @pytest.fixture
        def parser(self):
            return OutputParser()

        def test_error_patterns(self, parser):
            """Test recognition of error patterns."""
            assert parser.is_error_message("Error: something went wrong")
            assert parser.is_error_message("Operation failed")
            assert parser.is_error_message("Exception occurred")
            assert parser.is_error_message("File not found")
            assert parser.is_error_message("Permission denied")
            assert parser.is_error_message("Connection timeout")

        def test_non_error_messages(self, parser):
            """Test non-error messages."""
            assert not parser.is_error_message("Processing...")
            assert not parser.is_error_message("Hello World")
            assert not parser.is_error_message("Success")

        def test_case_insensitive(self, parser):
            """Test case insensitive matching."""
            assert parser.is_error_message("ERROR")
            assert parser.is_error_message("FAILED")

        def test_with_ansi_codes(self, parser):
            """Test with ANSI codes."""
            assert parser.is_error_message("\x1b[31mError\x1b[0m")


class TestParseTableMultilineEdgeCases:
    """Additional tests for parse_table multi-line cell handling."""

    @pytest.fixture
    def parser(self):
        return OutputParser()

    def test_multiline_cell_continuation(self, parser):
        """Test parsing table with multi-line cell content (covers lines 106-111)."""
        # Table where content spans multiple rows within a cell
        # Note: continuation rows need content in cells to merge
        table = """
│ Name     │ Description     │
├──────────┼─────────────────┤
│ Widget   │ A very long     │
│ cont     │ description     │
├──────────┼─────────────────┤
│ Gadget   │ Short desc      │
└──────────┴─────────────────┘
"""
        result = parser.parse_table(table)
        assert result is not None
        # Parser merges rows between separators
        assert len(result.rows) >= 1
        # Check that we can parse the table structure
        assert "Name" in result.headers
        assert "Description" in result.headers

    def test_last_row_without_bottom_separator(self, parser):
        """Test parsing table where last row ends without separator (covers lines 115-118)."""
        # Table without a closing separator after last row
        table = """
│ ID │ Value │
├────┼───────┤
│ 1  │ one   │
├────┼───────┤
│ 2  │ two   │
├────┼───────┤
│ 3  │ three │"""
        result = parser.parse_table(table)
        assert result is not None
        # The last row should be captured even without bottom border
        assert len(result.rows) == 3
        assert result.rows[2]["ID"] == "3"
        assert result.rows[2]["Value"] == "three"

    def test_multiline_with_content_continuation(self, parser):
        """Test multi-line cells with content in continuation rows."""
        table = """
│ ID │ Notes        │
├────┼──────────────┤
│ 1  │ First note   │
│ 1b │ Second note  │
├────┼──────────────┤
│ 2  │ Single note  │
"""
        result = parser.parse_table(table)
        assert result is not None
        # Parser should handle rows between separators
        assert "Notes" in result.headers


class TestParseMailcraftListEdgeCases:
    """Additional tests for parse_mailcraft_list edge cases."""

    @pytest.fixture
    def parser(self):
        return OutputParser()

    def test_multiple_emails_with_status_transitions(self, parser):
        """Test parsing multiple emails where new email starts with status (covers line 166)."""
        output = """
user@example.com - INBOX
│ ●    │ first@ex.com  │ First email    │ Today    │
├──────┼───────────────┼────────────────┼──────────┤
│ ○    │ second@ex.com │ Second email   │ Yesterday│
├──────┼───────────────┼────────────────┼──────────┤
│ NEW  │ third@ex.com  │ Third email    │ Last week│
"""
        result = parser.parse_mailcraft_list(output)
        assert len(result) == 3
        assert result[0]["from"] == "first@ex.com"
        assert result[1]["from"] == "second@ex.com"
        assert result[2]["from"] == "third@ex.com"

    def test_last_email_captured(self, parser):
        """Test that last email entry is captured (covers line 184)."""
        output = """
user@example.com - INBOX
│ NEW │ only@ex.com │ Only email │ Today │"""
        result = parser.parse_mailcraft_list(output)
        assert len(result) == 1
        assert result[0]["from"] == "only@ex.com"
        assert result[0]["subject"] == "Only email"

    def test_emails_separated_by_separators(self, parser):
        """Test parsing emails separated by table separators."""
        output = """
user@example.com - INBOX
┌────────┬──────────────┬─────────────┬────────────┐
│ Status │ From         │ Subject     │ Date       │
├────────┼──────────────┼─────────────┼────────────┤
│ ●      │ alice@ex.com │ Hello       │ 2024-01-01 │
├────────┼──────────────┼─────────────┼────────────┤
│ ○      │ bob@ex.com   │ Test        │ 2024-01-02 │
└────────┴──────────────┴─────────────┴────────────┘
"""
        result = parser.parse_mailcraft_list(output)
        # Should parse both emails
        assert len(result) >= 2
