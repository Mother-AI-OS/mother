"""IMAP client for email plugin.

Provides email reading capabilities via IMAP.
"""

from __future__ import annotations

import email
import email.header
import email.utils
import imaplib
from dataclasses import dataclass
from datetime import datetime
from email.message import Message
from typing import Any

from ....config.email_accounts import EmailAccount, get_password


@dataclass
class EmailMessage:
    """Represents an email message."""

    uid: str
    subject: str
    sender: str
    recipients: list[str]
    date: datetime | None
    body_text: str
    body_html: str
    attachments: list[dict[str, Any]]
    flags: list[str]
    folder: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "uid": self.uid,
            "subject": self.subject,
            "sender": self.sender,
            "recipients": self.recipients,
            "date": self.date.isoformat() if self.date else None,
            "body_text": self.body_text,
            "body_html": self.body_html,
            "attachments": self.attachments,
            "flags": self.flags,
            "folder": self.folder,
        }

    def summary(self) -> dict[str, Any]:
        """Return a summary without full body content."""
        return {
            "uid": self.uid,
            "subject": self.subject,
            "sender": self.sender,
            "date": self.date.isoformat() if self.date else None,
            "has_attachments": len(self.attachments) > 0,
            "flags": self.flags,
        }


def decode_header_value(value: str | None) -> str:
    """Decode a possibly encoded email header value."""
    if not value:
        return ""
    decoded_parts = []
    for part, encoding in email.header.decode_header(value):
        if isinstance(part, bytes):
            decoded_parts.append(part.decode(encoding or "utf-8", errors="replace"))
        else:
            decoded_parts.append(part)
    return "".join(decoded_parts)


def parse_date(date_str: str | None) -> datetime | None:
    """Parse an email date string."""
    if not date_str:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(date_str)
        return parsed
    except Exception:
        return None


def extract_body(msg: Message) -> tuple[str, str]:
    """Extract text and HTML body from message."""
    text_body = ""
    html_body = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))

            # Skip attachments
            if "attachment" in content_disposition:
                continue

            if content_type == "text/plain" and not text_body:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    text_body = payload.decode(charset, errors="replace")
            elif content_type == "text/html" and not html_body:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    html_body = payload.decode(charset, errors="replace")
    else:
        content_type = msg.get_content_type()
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            decoded = payload.decode(charset, errors="replace")
            if content_type == "text/html":
                html_body = decoded
            else:
                text_body = decoded

    return text_body, html_body


def extract_attachments(msg: Message) -> list[dict[str, Any]]:
    """Extract attachment info from message."""
    attachments = []

    if msg.is_multipart():
        for part in msg.walk():
            content_disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in content_disposition:
                filename = part.get_filename()
                if filename:
                    filename = decode_header_value(filename)
                attachments.append({
                    "filename": filename or "unknown",
                    "content_type": part.get_content_type(),
                    "size": len(part.get_payload(decode=True) or b""),
                })

    return attachments


def parse_message(uid: str, raw_email: bytes, folder: str) -> EmailMessage:
    """Parse a raw email into an EmailMessage."""
    msg = email.message_from_bytes(raw_email)

    subject = decode_header_value(msg.get("Subject"))
    sender = decode_header_value(msg.get("From"))
    to_header = decode_header_value(msg.get("To"))
    recipients = [r.strip() for r in to_header.split(",")] if to_header else []
    date = parse_date(msg.get("Date"))
    text_body, html_body = extract_body(msg)
    attachments = extract_attachments(msg)

    return EmailMessage(
        uid=uid,
        subject=subject,
        sender=sender,
        recipients=recipients,
        date=date,
        body_text=text_body,
        body_html=html_body,
        attachments=attachments,
        flags=[],
        folder=folder,
    )


class IMAPClient:
    """IMAP client for reading emails."""

    def __init__(self, account: EmailAccount):
        """Initialize IMAP client.

        Args:
            account: Email account configuration
        """
        self.account = account
        self._connection: imaplib.IMAP4 | imaplib.IMAP4_SSL | None = None

    def connect(self) -> None:
        """Connect to the IMAP server."""
        if not self.account.imap:
            raise ValueError(f"No IMAP config for account: {self.account.name}")

        password = get_password(self.account.name)
        if not password:
            raise ValueError(f"No password found for account: {self.account.name}")

        imap = self.account.imap
        if imap.use_ssl:
            self._connection = imaplib.IMAP4_SSL(imap.host, imap.port)
        else:
            self._connection = imaplib.IMAP4(imap.host, imap.port)
            if imap.use_starttls:
                self._connection.starttls()

        self._connection.login(self.account.email, password)

    def disconnect(self) -> None:
        """Disconnect from the server."""
        if self._connection:
            try:
                self._connection.close()
            except Exception:
                pass
            try:
                self._connection.logout()
            except Exception:
                pass
            self._connection = None

    def __enter__(self) -> "IMAPClient":
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.disconnect()

    def list_folders(self) -> list[str]:
        """List all available folders/mailboxes."""
        if not self._connection:
            raise ValueError("Not connected")

        _, folders = self._connection.list()
        result = []
        for folder in folders:
            if isinstance(folder, bytes):
                # Parse folder response: (flags) "delimiter" "name"
                parts = folder.decode().split(' "')
                if len(parts) >= 3:
                    name = parts[-1].strip('"')
                    result.append(name)
        return result

    def select_folder(self, folder: str = "INBOX") -> int:
        """Select a folder and return message count."""
        if not self._connection:
            raise ValueError("Not connected")

        status, data = self._connection.select(folder)
        if status != "OK":
            raise ValueError(f"Failed to select folder: {folder}")

        return int(data[0])

    def search(
        self,
        folder: str = "INBOX",
        criteria: str = "ALL",
        limit: int = 50,
    ) -> list[str]:
        """Search for messages matching criteria.

        Args:
            folder: Folder to search in
            criteria: IMAP search criteria (e.g., "UNSEEN", "FROM sender@example.com")
            limit: Maximum number of results

        Returns:
            List of message UIDs
        """
        if not self._connection:
            raise ValueError("Not connected")

        self.select_folder(folder)
        status, data = self._connection.uid("search", None, criteria)
        if status != "OK":
            raise ValueError(f"Search failed: {criteria}")

        uids = data[0].split()
        # Return most recent first, limited
        uids = uids[-limit:][::-1]
        return [uid.decode() for uid in uids]

    def fetch_message(self, uid: str, folder: str = "INBOX") -> EmailMessage:
        """Fetch a single message by UID.

        Args:
            uid: Message UID
            folder: Folder containing the message

        Returns:
            Parsed EmailMessage
        """
        if not self._connection:
            raise ValueError("Not connected")

        self.select_folder(folder)
        status, data = self._connection.uid("fetch", uid, "(RFC822 FLAGS)")
        if status != "OK" or not data[0]:
            raise ValueError(f"Failed to fetch message: {uid}")

        # Parse response
        raw_email = data[0][1]
        flags_data = data[0][0]

        message = parse_message(uid, raw_email, folder)

        # Extract flags
        if isinstance(flags_data, bytes):
            flags_str = flags_data.decode()
            if "FLAGS" in flags_str:
                import re
                match = re.search(r"FLAGS \(([^)]*)\)", flags_str)
                if match:
                    message.flags = match.group(1).split()

        return message

    def fetch_messages(
        self,
        folder: str = "INBOX",
        criteria: str = "ALL",
        limit: int = 20,
    ) -> list[EmailMessage]:
        """Fetch multiple messages.

        Args:
            folder: Folder to search
            criteria: IMAP search criteria
            limit: Maximum messages to return

        Returns:
            List of parsed messages
        """
        uids = self.search(folder, criteria, limit)
        messages = []
        for uid in uids:
            try:
                msg = self.fetch_message(uid, folder)
                messages.append(msg)
            except Exception:
                continue  # Skip failed messages
        return messages

    def mark_read(self, uid: str, folder: str = "INBOX") -> bool:
        """Mark a message as read."""
        if not self._connection:
            raise ValueError("Not connected")

        self.select_folder(folder)
        status, _ = self._connection.uid("store", uid, "+FLAGS", "\\Seen")
        return status == "OK"

    def mark_unread(self, uid: str, folder: str = "INBOX") -> bool:
        """Mark a message as unread."""
        if not self._connection:
            raise ValueError("Not connected")

        self.select_folder(folder)
        status, _ = self._connection.uid("store", uid, "-FLAGS", "\\Seen")
        return status == "OK"

    def delete_message(self, uid: str, folder: str = "INBOX") -> bool:
        """Mark a message for deletion."""
        if not self._connection:
            raise ValueError("Not connected")

        self.select_folder(folder)
        status, _ = self._connection.uid("store", uid, "+FLAGS", "\\Deleted")
        if status == "OK":
            self._connection.expunge()
            return True
        return False

    def move_message(self, uid: str, from_folder: str, to_folder: str) -> bool:
        """Move a message to another folder."""
        if not self._connection:
            raise ValueError("Not connected")

        self.select_folder(from_folder)
        # Copy then delete
        status, _ = self._connection.uid("copy", uid, to_folder)
        if status == "OK":
            return self.delete_message(uid, from_folder)
        return False

    def get_unread_count(self, folder: str = "INBOX") -> int:
        """Get count of unread messages in a folder."""
        if not self._connection:
            raise ValueError("Not connected")

        self.select_folder(folder)
        status, data = self._connection.uid("search", None, "UNSEEN")
        if status != "OK":
            return 0
        return len(data[0].split())
