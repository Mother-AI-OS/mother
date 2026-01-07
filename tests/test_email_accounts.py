"""Tests for the email accounts module."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mother.config import email_accounts
from mother.config.email_accounts import (
    EMAIL_ACCOUNTS_FILE,
    PROVIDER_PRESETS,
    EmailAccount,
    EmailAccountStore,
    ServerConfig,
)


class TestServerConfig:
    """Tests for ServerConfig dataclass."""

    def test_basic_config(self):
        """Test basic server config creation."""
        config = ServerConfig(host="imap.example.com", port=993)
        assert config.host == "imap.example.com"
        assert config.port == 993
        assert config.use_ssl is True
        assert config.use_starttls is False

    def test_config_with_all_options(self):
        """Test server config with all options."""
        config = ServerConfig(
            host="smtp.example.com",
            port=587,
            use_ssl=False,
            use_starttls=True,
        )
        assert config.host == "smtp.example.com"
        assert config.port == 587
        assert config.use_ssl is False
        assert config.use_starttls is True


class TestEmailAccount:
    """Tests for EmailAccount dataclass."""

    def test_basic_account(self):
        """Test basic account creation."""
        account = EmailAccount(name="personal", email="user@example.com")
        assert account.name == "personal"
        assert account.email == "user@example.com"
        assert account.display_name == ""
        assert account.imap is None
        assert account.smtp is None
        assert account.default is False

    def test_account_with_servers(self):
        """Test account with server configs."""
        imap = ServerConfig("imap.example.com", 993)
        smtp = ServerConfig("smtp.example.com", 465)
        account = EmailAccount(
            name="work",
            email="work@example.com",
            display_name="Work Email",
            imap=imap,
            smtp=smtp,
            default=True,
        )
        assert account.name == "work"
        assert account.imap.host == "imap.example.com"
        assert account.smtp.host == "smtp.example.com"
        assert account.default is True

    def test_to_dict(self):
        """Test conversion to dictionary."""
        imap = ServerConfig("imap.example.com", 993)
        account = EmailAccount(
            name="test",
            email="test@example.com",
            display_name="Test User",
            imap=imap,
            default=True,
        )
        data = account.to_dict()
        assert data["email"] == "test@example.com"
        assert data["display_name"] == "Test User"
        assert data["default"] is True
        assert data["imap"]["host"] == "imap.example.com"
        assert "smtp" not in data

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "email": "user@example.com",
            "display_name": "User",
            "imap": {"host": "imap.example.com", "port": 993, "use_ssl": True, "use_starttls": False},
            "default": True,
        }
        account = EmailAccount.from_dict("myaccount", data)
        assert account.name == "myaccount"
        assert account.email == "user@example.com"
        assert account.imap.host == "imap.example.com"
        assert account.default is True


class TestEmailAccountStore:
    """Tests for EmailAccountStore."""

    @pytest.fixture
    def temp_store(self, tmp_path):
        """Create a temporary email account store."""
        config_file = tmp_path / "email_accounts.yaml"
        store = EmailAccountStore(config_file)
        return store

    def test_list_accounts_empty(self, temp_store):
        """Test listing accounts when none exist."""
        accounts = temp_store.list_accounts()
        assert accounts == []

    def test_add_and_get_account(self, temp_store):
        """Test adding and retrieving an account."""
        imap = ServerConfig("imap.gmail.com", 993)
        smtp = ServerConfig("smtp.gmail.com", 465)
        account = EmailAccount(
            name="personal",
            email="user@gmail.com",
            imap=imap,
            smtp=smtp,
            default=True,
        )

        # Mock keyring to avoid system keyring dependency in tests
        with patch.object(email_accounts, "KEYRING_AVAILABLE", False):
            result = temp_store.add_account(account, "secret_password")
            assert result is True

            # Retrieve account
            retrieved = temp_store.get_account("personal")
            assert retrieved is not None
            assert retrieved.email == "user@gmail.com"
            assert retrieved.imap.host == "imap.gmail.com"

            # Check password stored in file fallback
            password = temp_store.get_password("personal")
            assert password == "secret_password"

    def test_list_multiple_accounts(self, temp_store):
        """Test listing multiple accounts."""
        with patch.object(email_accounts, "KEYRING_AVAILABLE", False):
            for name in ["account1", "account2", "account3"]:
                account = EmailAccount(name=name, email=f"{name}@example.com")
                temp_store.add_account(account, "password")

            accounts = temp_store.list_accounts()
            assert len(accounts) == 3
            names = [a.name for a in accounts]
            assert "account1" in names
            assert "account2" in names
            assert "account3" in names

    def test_remove_account(self, temp_store):
        """Test removing an account."""
        with patch.object(email_accounts, "KEYRING_AVAILABLE", False):
            account = EmailAccount(name="toremove", email="remove@example.com")
            temp_store.add_account(account, "password")

            assert temp_store.get_account("toremove") is not None
            result = temp_store.remove_account("toremove")
            assert result is True
            assert temp_store.get_account("toremove") is None

    def test_remove_nonexistent_account(self, temp_store):
        """Test removing a non-existent account."""
        result = temp_store.remove_account("nonexistent")
        assert result is False

    def test_get_default_account(self, temp_store):
        """Test getting the default account."""
        with patch.object(email_accounts, "KEYRING_AVAILABLE", False):
            # Add non-default account
            account1 = EmailAccount(name="acc1", email="acc1@example.com")
            temp_store.add_account(account1, "pass1")

            # Add default account
            account2 = EmailAccount(name="acc2", email="acc2@example.com", default=True)
            temp_store.add_account(account2, "pass2")

            default = temp_store.get_default_account()
            assert default is not None
            assert default.name == "acc2"

    def test_get_default_fallback(self, temp_store):
        """Test getting default when none set."""
        with patch.object(email_accounts, "KEYRING_AVAILABLE", False):
            account = EmailAccount(name="only", email="only@example.com")
            temp_store.add_account(account, "password")

            # Should return first account when no default
            default = temp_store.get_default_account()
            assert default is not None
            assert default.name == "only"

    def test_set_default(self, temp_store):
        """Test setting an account as default."""
        with patch.object(email_accounts, "KEYRING_AVAILABLE", False):
            # Add two accounts
            for name in ["acc1", "acc2"]:
                account = EmailAccount(name=name, email=f"{name}@example.com")
                temp_store.add_account(account, "password")

            # Set acc2 as default
            result = temp_store.set_default("acc2")
            assert result is True

            # Verify
            default = temp_store.get_default_account()
            assert default.name == "acc2"

    def test_set_default_nonexistent(self, temp_store):
        """Test setting default on nonexistent account."""
        result = temp_store.set_default("nonexistent")
        assert result is False


class TestProviderPresets:
    """Tests for email provider presets."""

    def test_gmail_preset(self):
        """Test Gmail preset values."""
        preset = PROVIDER_PRESETS["gmail"]
        assert preset["imap"].host == "imap.gmail.com"
        assert preset["imap"].port == 993
        assert preset["smtp"].host == "smtp.gmail.com"
        assert preset["smtp"].port == 465

    def test_outlook_preset(self):
        """Test Outlook preset values."""
        preset = PROVIDER_PRESETS["outlook"]
        assert preset["imap"].host == "outlook.office365.com"
        assert preset["smtp"].host == "smtp.office365.com"
        assert preset["smtp"].use_starttls is True

    def test_custom_preset(self):
        """Test custom preset is empty."""
        preset = PROVIDER_PRESETS["custom"]
        assert preset["imap"] is None
        assert preset["smtp"] is None

    def test_all_presets_have_notes(self):
        """Test all presets have helpful notes."""
        for name, preset in PROVIDER_PRESETS.items():
            assert "note" in preset, f"Preset {name} missing note"


class TestModuleFunctions:
    """Tests for module-level convenience functions."""

    @pytest.fixture
    def temp_store(self, tmp_path, monkeypatch):
        """Set up a temporary store for module functions."""
        config_file = tmp_path / "email_accounts.yaml"
        store = EmailAccountStore(config_file)

        # Patch the global store
        monkeypatch.setattr(email_accounts, "_store", store)
        return store

    def test_list_accounts_function(self, temp_store):
        """Test list_accounts module function."""
        with patch.object(email_accounts, "KEYRING_AVAILABLE", False):
            account = EmailAccount(name="test", email="test@example.com")
            temp_store.add_account(account, "password")

            accounts = email_accounts.list_accounts()
            assert len(accounts) == 1

    def test_get_account_function(self, temp_store):
        """Test get_account module function."""
        with patch.object(email_accounts, "KEYRING_AVAILABLE", False):
            account = EmailAccount(name="myacc", email="my@example.com")
            temp_store.add_account(account, "password")

            retrieved = email_accounts.get_account("myacc")
            assert retrieved is not None
            assert retrieved.email == "my@example.com"

    def test_get_password_function(self, temp_store):
        """Test get_password module function."""
        with patch.object(email_accounts, "KEYRING_AVAILABLE", False):
            account = EmailAccount(name="secure", email="secure@example.com")
            temp_store.add_account(account, "super_secret")

            password = email_accounts.get_password("secure")
            assert password == "super_secret"
