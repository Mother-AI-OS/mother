"""Output parsers for CLI tool output."""

import re
from dataclasses import dataclass
from typing import Any, Optional


# ANSI escape code pattern
ANSI_PATTERN = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

# Box drawing characters used by Rich (comprehensive set)
BOX_CHARS = "─│┌┐└┘├┤┬┴┼═║╔╗╚╝╠╣╦╩╬┃┏┓┗┛┡┩┢┪━┯┷┠┨╭╮╯╰"


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    return ANSI_PATTERN.sub("", text)


@dataclass
class TableParseResult:
    """Result of parsing a Rich table."""

    headers: list[str]
    rows: list[dict[str, Any]]
    title: Optional[str] = None


class OutputParser:
    """Parser for CLI output formats."""

    def is_separator_line(self, line: str) -> bool:
        """Check if line is a table separator (horizontal line only)."""
        clean = strip_ansi(line).strip()
        # Check if mostly horizontal separators (─, ━, ═) and corners/connectors
        horiz_chars = set("─━═┌┐└┘├┤┬┴┼╔╗╚╝╠╣╦╩╬┏┓┗┛┡┩┢┪┯┷╭╮╯╰")
        non_space = [c for c in clean if not c.isspace()]
        if not non_space:
            return False
        return all(c in horiz_chars for c in non_space)

    def get_cell_separator(self, line: str) -> Optional[str]:
        """Find the cell separator character in a line."""
        for sep in ["┃", "│", "║"]:
            if sep in line:
                return sep
        return None

    def parse_table(self, output: str) -> Optional[TableParseResult]:
        """Parse Rich table output into structured data."""
        lines = output.split("\n")

        title = None
        headers = []
        rows = []
        current_row_cells = []
        header_found = False
        sep_char = None

        for i, line in enumerate(lines):
            clean = strip_ansi(line).strip()

            # Skip empty lines
            if not clean:
                continue

            # Skip separator lines
            if self.is_separator_line(line):
                # If we have accumulated cells and headers, save the row
                if current_row_cells and header_found:
                    if len(current_row_cells) == len(headers):
                        # Merge multi-line cells
                        row = {}
                        for j, h in enumerate(headers):
                            row[h] = current_row_cells[j].strip()
                        rows.append(row)
                    current_row_cells = []
                continue

            # Find separator character
            if not sep_char:
                sep_char = self.get_cell_separator(clean)

            # Detect title (centered text before table)
            if not sep_char and clean:
                title = clean
                continue

            # Parse table content
            if sep_char and sep_char in clean:
                # Split by separator and clean up
                cells = [c.strip() for c in clean.split(sep_char)]
                # Remove empty edge cells
                cells = [c for c in cells if c or cells.index(c) not in [0, len(cells)-1]]
                cells = [c.strip() for c in cells]

                if not header_found:
                    # First content row is headers
                    headers = [c for c in cells if c]
                    header_found = True
                elif cells:
                    # Data row - handle multi-line cells
                    if not current_row_cells:
                        current_row_cells = cells
                    else:
                        # Continuation of previous row (multi-line cell)
                        for j, cell in enumerate(cells):
                            if j < len(current_row_cells) and cell:
                                if current_row_cells[j]:
                                    current_row_cells[j] += " " + cell
                                else:
                                    current_row_cells[j] = cell

        # Don't forget last row
        if current_row_cells and header_found and len(current_row_cells) == len(headers):
            row = {}
            for j, h in enumerate(headers):
                row[h] = current_row_cells[j].strip()
            rows.append(row)

        if headers:
            return TableParseResult(
                headers=headers,
                rows=rows,
                title=title,
            )

        return None

    def parse_mailcraft_list(self, output: str) -> list[dict[str, Any]]:
        """Parse mailcraft list output specifically."""
        emails = []
        clean = strip_ansi(output)
        lines = clean.split("\n")

        # Find account/folder header
        account_folder = None
        for line in lines:
            line = line.strip()
            if "@" in line and ("INBOX" in line or "Sent" in line or "Drafts" in line):
                account_folder = line
                break

        # Look for table rows - mailcraft uses ┃ or │
        current_email = {}
        for line in lines:
            line = line.strip()

            # Skip separators
            if not line or self.is_separator_line(line):
                if current_email:
                    emails.append(current_email)
                    current_email = {}
                continue

            # Parse data rows (contain │ or ┃)
            sep = self.get_cell_separator(line)
            if sep and line.count(sep) >= 2:
                parts = [p.strip() for p in line.split(sep)]
                parts = [p for p in parts if p]  # Remove empty

                if len(parts) >= 3:
                    # Check if this is a continuation or new row
                    # New rows typically have content in first column (status/id)
                    first_has_content = bool(parts[0]) if parts else False

                    if first_has_content or not current_email:
                        if current_email:
                            emails.append(current_email)
                        current_email = {
                            "status": parts[0] if len(parts) > 0 else "",
                            "from": parts[1] if len(parts) > 1 else "",
                            "subject": parts[2] if len(parts) > 2 else "",
                            "date": parts[3] if len(parts) > 3 else "",
                        }
                    else:
                        # Continuation - append to from/subject
                        if len(parts) > 1 and parts[1]:
                            current_email["from"] = (current_email.get("from", "") + " " + parts[1]).strip()
                        if len(parts) > 2 and parts[2]:
                            current_email["subject"] = (current_email.get("subject", "") + " " + parts[2]).strip()
                        if len(parts) > 3 and parts[3]:
                            current_email["date"] = (current_email.get("date", "") + " " + parts[3]).strip()

        # Don't forget last email
        if current_email:
            emails.append(current_email)

        return emails

    def extract_key_values(self, output: str) -> dict[str, str]:
        """Extract key-value pairs from formatted output."""
        result = {}
        clean = strip_ansi(output)

        # Pattern: "Key: Value" or "Key   Value"
        patterns = [
            r"^([A-Za-z][A-Za-z0-9\s\-_]+?):\s*(.+)$",
            r"^([A-Za-z][A-Za-z0-9\s\-_]+?)\s{2,}(.+)$",
        ]

        for line in clean.split("\n"):
            line = line.strip()

            for pattern in patterns:
                match = re.match(pattern, line)
                if match:
                    key = match.group(1).strip()
                    value = match.group(2).strip()
                    result[key] = value
                    break

        return result

    def extract_summary(self, output: str) -> dict[str, Any]:
        """Extract summary statistics from output."""
        clean = strip_ansi(output)
        result = {}

        # Common patterns for counts
        patterns = [
            (r"(\d+)\s+messages?", "messages"),
            (r"(\d+)\s+new", "new"),
            (r"(\d+)\s+accounts?", "accounts"),
            (r"(\d+)\s+leads?", "leads"),
            (r"(\d+)\s+documents?", "documents"),
            (r"(\d+)\s+results?", "results"),
            (r"Found\s+(\d+)", "found"),
            (r"Total:\s*(\d+)", "total"),
        ]

        for pattern, key in patterns:
            match = re.search(pattern, clean, re.IGNORECASE)
            if match:
                result[key] = int(match.group(1))

        return result

    def extract_email_header(self, output: str) -> dict[str, str]:
        """Extract email header fields from read output."""
        clean = strip_ansi(output)
        result = {}

        header_patterns = {
            "from": r"From:\s*(.+)",
            "to": r"To:\s*(.+)",
            "cc": r"CC:\s*(.+)",
            "date": r"Date:\s*(.+)",
            "subject": r"Subject:\s*(.+)",
        }

        for key, pattern in header_patterns.items():
            match = re.search(pattern, clean, re.IGNORECASE)
            if match:
                result[key] = match.group(1).strip()

        return result

    def extract_body(self, output: str, after_marker: str = "Message") -> str:
        """Extract body text after a marker."""
        clean = strip_ansi(output)

        # Look for marker line
        marker_pattern = rf"{after_marker}\s*[\─═]+\s*\n"
        match = re.search(marker_pattern, clean)

        if match:
            return clean[match.end() :].strip()

        # Fallback: return everything after blank line following headers
        lines = clean.split("\n")
        found_blank = False
        body_lines = []

        for line in lines:
            if not line.strip() and not found_blank:
                found_blank = True
                continue
            if found_blank:
                body_lines.append(line)

        return "\n".join(body_lines).strip()

    def is_success_message(self, output: str) -> bool:
        """Check if output indicates success."""
        clean = strip_ansi(output).lower()
        success_patterns = [
            "success",
            "completed",
            "done",
            "sent",
            "created",
            "saved",
            "moved",
            "deleted",
        ]
        return any(pattern in clean for pattern in success_patterns)

    def is_error_message(self, output: str) -> bool:
        """Check if output indicates an error."""
        clean = strip_ansi(output).lower()
        error_patterns = [
            "error",
            "failed",
            "exception",
            "not found",
            "permission denied",
            "timeout",
        ]
        return any(pattern in clean for pattern in error_patterns)
