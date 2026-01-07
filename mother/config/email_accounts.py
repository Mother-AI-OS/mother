"""Email Account Storage.

Secure storage for email account configurations using keyring for passwords
and YAML for account metadata.
"""

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

# Try to import keyring, fall back to None if not available
try:
    import keyring

    KEYRING_AVAILABLE = True
except ImportError:
    keyring = None  # type: ignore
    KEYRING_AVAILABLE = False


# Config paths
CONFIG_DIR = Path.home() / ".config" / "mother"
EMAIL_ACCOUNTS_FILE = CONFIG_DIR / "email_accounts.yaml"
KEYRING_SERVICE = "mother.email"


@dataclass
class ServerConfig:
    """IMAP or SMTP server configuration."""

    host: str
    port: int
    use_ssl: bool = True
    use_starttls: bool = False


@dataclass
class EmailAccount:
    """Email account configuration."""

    name: str
    email: str
    display_name: str = ""
    imap: ServerConfig | None = None
    smtp: ServerConfig | None = None
    default: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        data = {
            "email": self.email,
            "display_name": self.display_name,
            "default": self.default,
        }
        if self.imap:
            data["imap"] = asdict(self.imap)
        if self.smtp:
            data["smtp"] = asdict(self.smtp)
        return data

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> "EmailAccount":
        """Create from dictionary."""
        imap_data = data.get("imap")
        smtp_data = data.get("smtp")
        return cls(
            name=name,
            email=data.get("email", ""),
            display_name=data.get("display_name", ""),
            imap=ServerConfig(**imap_data) if imap_data else None,
            smtp=ServerConfig(**smtp_data) if smtp_data else None,
            default=data.get("default", False),
        )


class EmailAccountStore:
    """Secure storage for email accounts."""

    def __init__(self, config_file: Path | None = None):
        """Initialize the store.

        Args:
            config_file: Path to YAML config file (default: ~/.config/mother/email_accounts.yaml)
        """
        self.config_file = config_file or EMAIL_ACCOUNTS_FILE
        self._ensure_config_dir()

    def _ensure_config_dir(self):
        """Ensure config directory exists with proper permissions."""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_accounts_data(self) -> dict[str, dict[str, Any]]:
        """Load raw account data from YAML."""
        if not self.config_file.exists():
            return {}
        try:
            with open(self.config_file) as f:
                data = yaml.safe_load(f) or {}
                return data.get("accounts", {})
        except Exception:
            return {}

    def _save_accounts_data(self, accounts: dict[str, dict[str, Any]]):
        """Save account data to YAML."""
        data = {"accounts": accounts}
        with open(self.config_file, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        # Set secure permissions
        os.chmod(self.config_file, 0o600)

    def list_accounts(self) -> list[EmailAccount]:
        """List all configured email accounts."""
        accounts_data = self._load_accounts_data()
        return [
            EmailAccount.from_dict(name, data)
            for name, data in accounts_data.items()
        ]

    def get_account(self, name: str) -> EmailAccount | None:
        """Get a specific account by name."""
        accounts_data = self._load_accounts_data()
        if name not in accounts_data:
            return None
        return EmailAccount.from_dict(name, accounts_data[name])

    def get_default_account(self) -> EmailAccount | None:
        """Get the default email account."""
        accounts = self.list_accounts()
        for account in accounts:
            if account.default:
                return account
        # Return first account if no default set
        return accounts[0] if accounts else None

    def add_account(self, account: EmailAccount, password: str) -> bool:
        """Add or update an email account.

        Args:
            account: Account configuration
            password: Account password (stored in keyring)

        Returns:
            True if successful
        """
        # Store password in keyring
        if KEYRING_AVAILABLE and keyring:
            try:
                keyring.set_password(KEYRING_SERVICE, account.name, password)
            except Exception as e:
                # Keyring failed, store password in file (less secure)
                print(f"Warning: Keyring unavailable ({e}), password stored in config")
                self._store_password_in_file(account.name, password)
        else:
            self._store_password_in_file(account.name, password)

        # Load existing accounts
        accounts_data = self._load_accounts_data()

        # If this is set as default, unset others
        if account.default:
            for name in accounts_data:
                accounts_data[name]["default"] = False

        # Add/update this account
        accounts_data[account.name] = account.to_dict()

        # Save
        self._save_accounts_data(accounts_data)
        return True

    def remove_account(self, name: str) -> bool:
        """Remove an email account.

        Args:
            name: Account name to remove

        Returns:
            True if removed, False if not found
        """
        accounts_data = self._load_accounts_data()
        if name not in accounts_data:
            return False

        # Remove password from keyring
        if KEYRING_AVAILABLE and keyring:
            try:
                keyring.delete_password(KEYRING_SERVICE, name)
            except Exception:
                pass  # Password might not exist in keyring

        # Remove password file if exists
        password_file = self.config_file.parent / ".email_passwords" / f"{name}.secret"
        if password_file.exists():
            password_file.unlink()

        # Remove from accounts
        del accounts_data[name]
        self._save_accounts_data(accounts_data)
        return True

    def get_password(self, name: str) -> str | None:
        """Get the password for an account.

        Args:
            name: Account name

        Returns:
            Password or None if not found
        """
        # Try keyring first
        if KEYRING_AVAILABLE and keyring:
            try:
                password = keyring.get_password(KEYRING_SERVICE, name)
                if password:
                    return password
            except Exception:
                pass

        # Fall back to file storage
        return self._get_password_from_file(name)

    def _store_password_in_file(self, name: str, password: str):
        """Store password in encrypted file (fallback)."""
        password_dir = self.config_file.parent / ".email_passwords"
        password_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(password_dir, 0o700)

        password_file = password_dir / f"{name}.secret"
        # Simple obfuscation (not real encryption, but better than plaintext)
        # For real security, use keyring or implement proper encryption
        import base64

        encoded = base64.b64encode(password.encode()).decode()
        password_file.write_text(encoded)
        os.chmod(password_file, 0o600)

    def _get_password_from_file(self, name: str) -> str | None:
        """Get password from file storage."""
        password_file = self.config_file.parent / ".email_passwords" / f"{name}.secret"
        if not password_file.exists():
            return None
        try:
            import base64

            encoded = password_file.read_text()
            return base64.b64decode(encoded.encode()).decode()
        except Exception:
            return None

    def set_default(self, name: str) -> bool:
        """Set an account as the default.

        Args:
            name: Account name

        Returns:
            True if successful, False if account not found
        """
        accounts_data = self._load_accounts_data()
        if name not in accounts_data:
            return False

        # Unset all defaults, set this one
        for account_name in accounts_data:
            accounts_data[account_name]["default"] = account_name == name

        self._save_accounts_data(accounts_data)
        return True


# Module-level convenience functions
_store: EmailAccountStore | None = None


def get_store() -> EmailAccountStore:
    """Get the global email account store."""
    global _store
    if _store is None:
        _store = EmailAccountStore()
    return _store


def list_accounts() -> list[EmailAccount]:
    """List all configured email accounts."""
    return get_store().list_accounts()


def get_account(name: str) -> EmailAccount | None:
    """Get a specific account by name."""
    return get_store().get_account(name)


def get_default_account() -> EmailAccount | None:
    """Get the default email account."""
    return get_store().get_default_account()


def add_account(account: EmailAccount, password: str) -> bool:
    """Add or update an email account."""
    return get_store().add_account(account, password)


def remove_account(name: str) -> bool:
    """Remove an email account."""
    return get_store().remove_account(name)


def get_password(name: str) -> str | None:
    """Get the password for an account."""
    return get_store().get_password(name)


# Common email provider presets
PROVIDER_PRESETS = {
    "gmail": {
        "imap": ServerConfig("imap.gmail.com", 993, use_ssl=True),
        "smtp": ServerConfig("smtp.gmail.com", 465, use_ssl=True),
        "note": "Use an App Password, not your Google password",
    },
    "outlook": {
        "imap": ServerConfig("outlook.office365.com", 993, use_ssl=True),
        "smtp": ServerConfig("smtp.office365.com", 587, use_ssl=False, use_starttls=True),
        "note": "May need to enable IMAP in Outlook settings",
    },
    "yahoo": {
        "imap": ServerConfig("imap.mail.yahoo.com", 993, use_ssl=True),
        "smtp": ServerConfig("smtp.mail.yahoo.com", 465, use_ssl=True),
        "note": "Use an App Password from Yahoo security settings",
    },
    "icloud": {
        "imap": ServerConfig("imap.mail.me.com", 993, use_ssl=True),
        "smtp": ServerConfig("smtp.mail.me.com", 587, use_ssl=False, use_starttls=True),
        "note": "Use an App-Specific Password from Apple ID settings",
    },
    "gmx": {
        "imap": ServerConfig("imap.gmx.net", 993, use_ssl=True),
        "smtp": ServerConfig("mail.gmx.net", 465, use_ssl=True),
        "note": "Enable IMAP in GMX settings",
    },
    "web.de": {
        "imap": ServerConfig("imap.web.de", 993, use_ssl=True),
        "smtp": ServerConfig("smtp.web.de", 587, use_ssl=False, use_starttls=True),
        "note": "Enable IMAP in web.de settings",
    },
    "custom": {
        "imap": None,
        "smtp": None,
        "note": "Enter custom server settings",
    },
}
