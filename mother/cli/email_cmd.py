"""Email Account Management CLI.

Commands for adding, listing, and managing email accounts.
"""

import sys
from getpass import getpass

from ..config.email_accounts import (
    EMAIL_ACCOUNTS_FILE,
    PROVIDER_PRESETS,
    EmailAccount,
    ServerConfig,
    add_account,
    get_account,
    get_password,
    get_store,
    list_accounts,
    remove_account,
)


def prompt(question: str, default: str | None = None, required: bool = True) -> str:
    """Prompt user for input with optional default."""
    if default:
        full_prompt = f"{question} [{default}]: "
    else:
        full_prompt = f"{question}: "

    while True:
        value = input(full_prompt).strip()
        if not value and default:
            return default
        if value or not required:
            return value
        print("  This field is required.")


def prompt_int(question: str, default: int | None = None) -> int:
    """Prompt for integer input."""
    while True:
        try:
            value = prompt(question, str(default) if default else None)
            return int(value)
        except ValueError:
            print("  Please enter a number.")


def prompt_yes_no(question: str, default: bool = True) -> bool:
    """Prompt for yes/no answer."""
    default_str = "Y/n" if default else "y/N"
    while True:
        value = input(f"{question} [{default_str}]: ").strip().lower()
        if not value:
            return default
        if value in ("y", "yes"):
            return True
        if value in ("n", "no"):
            return False
        print("  Please answer 'yes' or 'no'.")


def cmd_add() -> int:
    """Add a new email account interactively."""
    print("\n=== Add Email Account ===\n")

    # Account name
    name = prompt("Account name (e.g., 'personal', 'work')")

    # Check if exists
    if get_account(name):
        if not prompt_yes_no(f"Account '{name}' already exists. Update it?", default=False):
            print("Cancelled.")
            return 1

    # Email address
    email = prompt("Email address")

    # Display name (optional)
    display_name = prompt("Display name", default=email.split("@")[0], required=False)

    # Provider selection
    print("\nEmail provider:")
    providers = list(PROVIDER_PRESETS.keys())
    for i, provider in enumerate(providers, 1):
        print(f"  {i}. {provider.title()}")

    while True:
        try:
            choice = prompt_int("Select provider", default=len(providers))
            if 1 <= choice <= len(providers):
                provider = providers[choice - 1]
                break
            print(f"  Please enter 1-{len(providers)}")
        except ValueError:
            pass

    preset = PROVIDER_PRESETS[provider]

    # Show provider note if any
    if preset.get("note"):
        print(f"\n  Note: {preset['note']}")

    # IMAP settings
    if provider == "custom":
        print("\nIMAP Settings:")
        imap = ServerConfig(
            host=prompt("  IMAP host"),
            port=prompt_int("  IMAP port", default=993),
            use_ssl=prompt_yes_no("  Use SSL?", default=True),
        )
    else:
        imap = preset["imap"]

    # SMTP settings
    if provider == "custom":
        print("\nSMTP Settings:")
        smtp = ServerConfig(
            host=prompt("  SMTP host"),
            port=prompt_int("  SMTP port", default=465),
            use_ssl=prompt_yes_no("  Use SSL?", default=True),
            use_starttls=prompt_yes_no("  Use STARTTLS?", default=False) if not prompt_yes_no("  Use SSL?", default=True) else False,
        )
    else:
        smtp = preset["smtp"]

    # Password
    print()
    password = getpass("Email password (or app password): ")

    # Set as default?
    is_default = prompt_yes_no("\nSet as default account?", default=len(list_accounts()) == 0)

    # Create account
    account = EmailAccount(
        name=name,
        email=email,
        display_name=display_name,
        imap=imap,
        smtp=smtp,
        default=is_default,
    )

    # Save
    if add_account(account, password):
        print(f"\n✓ Account '{name}' saved successfully")
        print(f"  Email: {email}")
        print(f"  Config: {EMAIL_ACCOUNTS_FILE}")
        if is_default:
            print(f"  Status: Default account")
        return 0
    else:
        print("\n✗ Failed to save account")
        return 1


def cmd_list(show_passwords: bool = False) -> int:
    """List all configured email accounts."""
    accounts = list_accounts()

    if not accounts:
        print("No email accounts configured.")
        print("Run: mother email add")
        return 0

    print(f"\n{'Name':<20} {'Email':<35} {'Default':<10}")
    print("-" * 65)

    for account in accounts:
        default_str = "Yes" if account.default else ""
        print(f"{account.name:<20} {account.email:<35} {default_str:<10}")

    print(f"\nTotal: {len(accounts)} account(s)")
    print(f"Config: {EMAIL_ACCOUNTS_FILE}")
    return 0


def cmd_remove(name: str, yes: bool = False) -> int:
    """Remove an email account."""
    account = get_account(name)
    if not account:
        print(f"Account not found: {name}")
        return 1

    if not yes:
        if not prompt_yes_no(f"Remove account '{name}' ({account.email})?", default=False):
            print("Cancelled.")
            return 1

    if remove_account(name):
        print(f"✓ Account '{name}' removed")
        return 0
    else:
        print(f"✗ Failed to remove account")
        return 1


def cmd_test(name: str) -> int:
    """Test connection to an email account."""
    account = get_account(name)
    if not account:
        print(f"Account not found: {name}")
        return 1

    password = get_password(name)
    if not password:
        print(f"No password found for account: {name}")
        return 1

    print(f"\nTesting account: {name} ({account.email})")

    # Test IMAP
    if account.imap:
        print(f"\n  IMAP: {account.imap.host}:{account.imap.port}", end=" ")
        try:
            import imaplib

            if account.imap.use_ssl:
                imap = imaplib.IMAP4_SSL(account.imap.host, account.imap.port)
            else:
                imap = imaplib.IMAP4(account.imap.host, account.imap.port)
                if account.imap.use_starttls:
                    imap.starttls()

            imap.login(account.email, password)
            imap.select("INBOX")
            _, messages = imap.search(None, "ALL")
            count = len(messages[0].split())
            imap.close()
            imap.logout()
            print(f"✓ Connected ({count} messages)")
        except Exception as e:
            print(f"✗ Failed: {e}")
            return 1
    else:
        print("  IMAP: Not configured")

    # Test SMTP
    if account.smtp:
        print(f"  SMTP: {account.smtp.host}:{account.smtp.port}", end=" ")
        try:
            import smtplib

            if account.smtp.use_ssl:
                smtp = smtplib.SMTP_SSL(account.smtp.host, account.smtp.port)
            else:
                smtp = smtplib.SMTP(account.smtp.host, account.smtp.port)
                if account.smtp.use_starttls:
                    smtp.starttls()

            smtp.login(account.email, password)
            smtp.quit()
            print("✓ Connected")
        except Exception as e:
            print(f"✗ Failed: {e}")
            return 1
    else:
        print("  SMTP: Not configured")

    print(f"\n✓ Account '{name}' is working correctly")
    return 0


def cmd_info(name: str) -> int:
    """Show detailed account information."""
    account = get_account(name)
    if not account:
        print(f"Account not found: {name}")
        return 1

    print(f"\n=== Account: {name} ===")
    print(f"  Email: {account.email}")
    print(f"  Display Name: {account.display_name or '(not set)'}")
    print(f"  Default: {'Yes' if account.default else 'No'}")

    if account.imap:
        print(f"\n  IMAP Server:")
        print(f"    Host: {account.imap.host}")
        print(f"    Port: {account.imap.port}")
        print(f"    SSL: {account.imap.use_ssl}")
        print(f"    STARTTLS: {account.imap.use_starttls}")

    if account.smtp:
        print(f"\n  SMTP Server:")
        print(f"    Host: {account.smtp.host}")
        print(f"    Port: {account.smtp.port}")
        print(f"    SSL: {account.smtp.use_ssl}")
        print(f"    STARTTLS: {account.smtp.use_starttls}")

    has_password = get_password(name) is not None
    print(f"\n  Password: {'Stored' if has_password else 'Not found'}")

    return 0


def cmd_default(name: str) -> int:
    """Set an account as the default."""
    if get_store().set_default(name):
        print(f"✓ '{name}' is now the default account")
        return 0
    else:
        print(f"Account not found: {name}")
        return 1


def print_usage():
    """Print usage information."""
    print("""
Mother Email Account Manager

Usage: mother email <command> [args]

Commands:
  add                 Add a new email account (interactive)
  list                List all configured accounts
  remove <name>       Remove an email account
  test <name>         Test connection to an account
  info <name>         Show detailed account information
  default <name>      Set an account as the default

Examples:
  mother email add                    # Interactive setup
  mother email list                   # Show all accounts
  mother email test personal          # Test the 'personal' account
  mother email remove work            # Remove the 'work' account
  mother email default personal       # Set 'personal' as default
""")


def main(args: list[str] | None = None) -> int:
    """Main entry point for email command."""
    if args is None:
        args = sys.argv[1:]

    if not args or args[0] in ("--help", "-h"):
        print_usage()
        return 0

    command = args[0].lower()

    try:
        if command == "add":
            return cmd_add()
        elif command == "list":
            show_passwords = "--show" in args
            return cmd_list(show_passwords)
        elif command == "remove" or command == "rm":
            if len(args) < 2:
                print("Usage: mother email remove <name>")
                return 1
            yes = "-y" in args or "--yes" in args
            return cmd_remove(args[1], yes=yes)
        elif command == "test":
            if len(args) < 2:
                print("Usage: mother email test <name>")
                return 1
            return cmd_test(args[1])
        elif command == "info":
            if len(args) < 2:
                print("Usage: mother email info <name>")
                return 1
            return cmd_info(args[1])
        elif command == "default":
            if len(args) < 2:
                print("Usage: mother email default <name>")
                return 1
            return cmd_default(args[1])
        else:
            print(f"Unknown command: {command}")
            print_usage()
            return 1

    except KeyboardInterrupt:
        print("\nCancelled.")
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
