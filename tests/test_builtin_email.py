"""Tests for the built-in email plugin."""

import email
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from mother.config.email_accounts import EmailAccount, ServerConfig
from mother.plugins.builtin.email import EmailPlugin
from mother.plugins.builtin.email.imap_client import (
    EmailMessage,
    IMAPClient,
    decode_header_value,
    extract_attachments,
    extract_body,
    parse_date,
    parse_message,
)
from mother.plugins.builtin.email.smtp_client import EmailDraft, SMTPClient


class TestDecodeHeaderValue:
    """Tests for header decoding."""

    def test_plain_text(self):
        """Test plain text header."""
        result = decode_header_value("Hello World")
        assert result == "Hello World"

    def test_empty_value(self):
        """Test empty value."""
        result = decode_header_value("")
        assert result == ""

    def test_none_value(self):
        """Test None value."""
        result = decode_header_value(None)
        assert result == ""

    def test_encoded_utf8(self):
        """Test UTF-8 encoded header."""
        # =?UTF-8?Q?Test?= encoded header
        encoded = "=?UTF-8?Q?Test_Subject?="
        result = decode_header_value(encoded)
        assert "Test" in result


class TestParseDate:
    """Tests for date parsing."""

    def test_valid_date(self):
        """Test parsing valid date."""
        date_str = "Mon, 1 Jan 2024 12:00:00 +0000"
        result = parse_date(date_str)
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 1

    def test_invalid_date(self):
        """Test parsing invalid date."""
        result = parse_date("not a date")
        assert result is None

    def test_none_date(self):
        """Test parsing None."""
        result = parse_date(None)
        assert result is None


class TestEmailMessage:
    """Tests for EmailMessage dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        msg = EmailMessage(
            uid="123",
            subject="Test Subject",
            sender="sender@example.com",
            recipients=["recipient@example.com"],
            date=datetime(2024, 1, 1, 12, 0, 0),
            body_text="Hello World",
            body_html="",
            attachments=[],
            flags=["\\Seen"],
            folder="INBOX",
        )
        data = msg.to_dict()
        assert data["uid"] == "123"
        assert data["subject"] == "Test Subject"
        assert data["sender"] == "sender@example.com"
        assert data["date"] == "2024-01-01T12:00:00"

    def test_summary(self):
        """Test summary generation."""
        msg = EmailMessage(
            uid="123",
            subject="Test Subject",
            sender="sender@example.com",
            recipients=["recipient@example.com"],
            date=datetime(2024, 1, 1, 12, 0, 0),
            body_text="Hello World",
            body_html="",
            attachments=[{"filename": "test.pdf"}],
            flags=["\\Seen"],
            folder="INBOX",
        )
        summary = msg.summary()
        assert "body_text" not in summary
        assert summary["has_attachments"] is True
        assert summary["subject"] == "Test Subject"


class TestEmailDraft:
    """Tests for EmailDraft dataclass."""

    def test_from_dict_simple(self):
        """Test creation from simple dict."""
        data = {
            "to": "recipient@example.com",
            "subject": "Test",
            "body": "Hello",
        }
        draft = EmailDraft.from_dict(data)
        assert draft.to == ["recipient@example.com"]
        assert draft.subject == "Test"
        assert draft.body_text == "Hello"

    def test_from_dict_multiple_recipients(self):
        """Test creation with multiple recipients."""
        data = {
            "to": ["one@example.com", "two@example.com"],
            "subject": "Test",
            "body": "Hello",
            "cc": ["cc@example.com"],
        }
        draft = EmailDraft.from_dict(data)
        assert len(draft.to) == 2
        assert len(draft.cc) == 1

    def test_from_dict_with_html(self):
        """Test creation with HTML body."""
        data = {
            "to": "recipient@example.com",
            "subject": "Test",
            "body_text": "Plain text",
            "body_html": "<h1>HTML</h1>",
        }
        draft = EmailDraft.from_dict(data)
        assert draft.body_text == "Plain text"
        assert draft.body_html == "<h1>HTML</h1>"


class TestIMAPClient:
    """Tests for IMAPClient."""

    @pytest.fixture
    def account(self):
        """Create a test account."""
        return EmailAccount(
            name="test",
            email="test@example.com",
            imap=ServerConfig("imap.example.com", 993, use_ssl=True),
            smtp=ServerConfig("smtp.example.com", 465, use_ssl=True),
        )

    def test_init(self, account):
        """Test client initialization."""
        client = IMAPClient(account)
        assert client.account == account
        assert client._connection is None

    def test_no_imap_config(self):
        """Test error when no IMAP config."""
        account = EmailAccount(name="test", email="test@example.com")
        client = IMAPClient(account)
        with pytest.raises(ValueError, match="No IMAP config"):
            client.connect()

    @patch("mother.plugins.builtin.email.imap_client.get_password")
    def test_no_password(self, mock_get_password, account):
        """Test error when no password."""
        mock_get_password.return_value = None
        client = IMAPClient(account)
        with pytest.raises(ValueError, match="No password found"):
            client.connect()


class TestSMTPClient:
    """Tests for SMTPClient."""

    @pytest.fixture
    def account(self):
        """Create a test account."""
        return EmailAccount(
            name="test",
            email="test@example.com",
            display_name="Test User",
            imap=ServerConfig("imap.example.com", 993, use_ssl=True),
            smtp=ServerConfig("smtp.example.com", 465, use_ssl=True),
        )

    def test_init(self, account):
        """Test client initialization."""
        client = SMTPClient(account)
        assert client.account == account
        assert client._connection is None

    def test_no_smtp_config(self):
        """Test error when no SMTP config."""
        account = EmailAccount(name="test", email="test@example.com")
        client = SMTPClient(account)
        with pytest.raises(ValueError, match="No SMTP config"):
            client.connect()

    def test_build_message_simple(self, account):
        """Test building a simple message."""
        client = SMTPClient(account)
        draft = EmailDraft(
            to=["recipient@example.com"],
            subject="Test Subject",
            body_text="Hello World",
        )
        msg = client._build_message(draft)
        assert msg["To"] == "recipient@example.com"
        assert msg["Subject"] == "Test Subject"
        assert "Test User" in msg["From"]

    def test_build_message_with_cc(self, account):
        """Test building message with CC."""
        client = SMTPClient(account)
        draft = EmailDraft(
            to=["recipient@example.com"],
            subject="Test",
            body_text="Hello",
            cc=["cc@example.com"],
        )
        msg = client._build_message(draft)
        assert msg["Cc"] == "cc@example.com"


class TestEmailPlugin:
    """Tests for the EmailPlugin."""

    @pytest.fixture
    def plugin(self):
        """Create a plugin instance."""
        return EmailPlugin()

    def test_init(self, plugin):
        """Test plugin initialization."""
        assert plugin.manifest.plugin.name == "email"
        assert plugin.manifest.plugin.version == "1.0.0"

    def test_capabilities(self, plugin):
        """Test plugin capabilities are defined."""
        caps = plugin.get_capabilities()
        assert len(caps) == 10
        cap_names = [c.name for c in caps]
        assert "list_accounts" in cap_names
        assert "list_messages" in cap_names
        assert "send_message" in cap_names
        assert "read_message" in cap_names

    def test_send_requires_confirmation(self, plugin):
        """Test send_message requires confirmation."""
        caps = plugin.get_capabilities()
        send_cap = next(c for c in caps if c.name == "send_message")
        assert send_cap.confirmation_required is True

    def test_delete_requires_confirmation(self, plugin):
        """Test delete_message requires confirmation."""
        caps = plugin.get_capabilities()
        delete_cap = next(c for c in caps if c.name == "delete_message")
        assert delete_cap.confirmation_required is True

    @pytest.mark.asyncio
    async def test_list_accounts_no_accounts(self, plugin):
        """Test list_accounts when no accounts configured."""
        with patch("mother.plugins.builtin.email.list_accounts", return_value=[]):
            result = await plugin.execute("list_accounts", {})
            assert result.success is False
            assert result.error_code == "NOT_CONFIGURED"

    @pytest.mark.asyncio
    async def test_list_accounts_with_accounts(self, plugin):
        """Test list_accounts with configured accounts."""
        mock_accounts = [
            EmailAccount(
                name="personal",
                email="personal@example.com",
                default=True,
                imap=ServerConfig("imap.example.com", 993),
                smtp=ServerConfig("smtp.example.com", 465),
            ),
        ]
        with patch("mother.plugins.builtin.email.list_accounts", return_value=mock_accounts):
            result = await plugin.execute("list_accounts", {})
            assert result.success is True
            assert len(result.data["accounts"]) == 1
            assert result.data["accounts"][0]["name"] == "personal"

    @pytest.mark.asyncio
    async def test_unknown_capability(self, plugin):
        """Test unknown capability returns error."""
        result = await plugin.execute("unknown_capability", {})
        assert result.success is False
        assert result.error_code == "UNKNOWN_CAPABILITY"

    @pytest.mark.asyncio
    async def test_get_account_not_found(self, plugin):
        """Test error when account not found."""
        with patch("mother.plugins.builtin.email.get_account", return_value=None):
            result = await plugin.execute("list_folders", {"account": "nonexistent"})
            assert result.success is False
            assert "not found" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_get_default_account_none(self, plugin):
        """Test error when no default account."""
        with patch("mother.plugins.builtin.email.get_default_account", return_value=None):
            result = await plugin.execute("list_folders", {})
            assert result.success is False
            assert "mother email add" in result.error_message


class TestParseMessage:
    """Tests for message parsing."""

    def test_parse_simple_message(self):
        """Test parsing a simple email message."""
        raw = b"""From: sender@example.com
To: recipient@example.com
Subject: Test Subject
Date: Mon, 1 Jan 2024 12:00:00 +0000
Content-Type: text/plain

Hello World
"""
        msg = parse_message("123", raw, "INBOX")
        assert msg.uid == "123"
        assert msg.subject == "Test Subject"
        assert msg.sender == "sender@example.com"
        assert "Hello World" in msg.body_text

    def test_parse_multipart_message(self):
        """Test parsing a multipart message."""
        raw = b"""From: sender@example.com
To: recipient@example.com
Subject: Multipart Test
Date: Mon, 1 Jan 2024 12:00:00 +0000
MIME-Version: 1.0
Content-Type: multipart/alternative; boundary="boundary"

--boundary
Content-Type: text/plain

Plain text body
--boundary
Content-Type: text/html

<html><body>HTML body</body></html>
--boundary--
"""
        msg = parse_message("456", raw, "INBOX")
        assert "Plain text body" in msg.body_text
        assert "<html>" in msg.body_html
