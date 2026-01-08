"""Mother AI OS Setup Wizard.

Interactive first-time setup for configuring Mother on a new system.
"""

import sys
from getpass import getpass

from ..credentials import (
    CREDENTIALS_FILE,
    ensure_file_exists,
    read_credentials,
    set_credential,
)


def print_header():
    """Print setup wizard header."""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                    Mother AI OS Setup                        ║
║         AI Agent operating system via natural language       ║
╚══════════════════════════════════════════════════════════════╝
""")


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


def prompt_password(question: str) -> str:
    """Prompt for password (hidden input)."""
    while True:
        value = getpass(f"{question}: ").strip()
        if value:
            return value
        print("  This field is required.")


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


def setup_anthropic_key() -> bool:
    """Set up the Anthropic API key."""
    print("\n1. ANTHROPIC API KEY (Required)")
    print("   Get your key from: https://console.anthropic.com/settings/keys")
    print()

    existing = read_credentials().get("ANTHROPIC_API_KEY", "")
    if existing:
        print(f"   Current: {existing[:12]}...{existing[-4:]}")
        if not prompt_yes_no("   Update this key?", default=False):
            return True

    key = prompt_password("   Enter your Anthropic API key")
    if key.startswith("sk-ant-"):
        set_credential("ANTHROPIC_API_KEY", key)
        print("   ✓ Anthropic API key saved")
        return True
    else:
        print("   ⚠ Warning: Key doesn't match expected format (sk-ant-...)")
        if prompt_yes_no("   Save anyway?", default=False):
            set_credential("ANTHROPIC_API_KEY", key)
            return True
        return False


def setup_mother_api_key():
    """Set up the Mother API authentication key."""
    print("\n2. MOTHER API KEY (Recommended)")
    print("   This protects your Mother server from unauthorized access.")
    print()

    existing = read_credentials().get("MOTHER_API_KEY", "")
    if existing:
        print(f"   Current: {existing[:8]}...{existing[-4:] if len(existing) > 12 else ''}")
        if not prompt_yes_no("   Update this key?", default=False):
            return

    if prompt_yes_no("   Generate a random API key?", default=True):
        import secrets

        key = f"mother_{secrets.token_urlsafe(32)}"
        set_credential("MOTHER_API_KEY", key)
        print(f"   ✓ Generated: {key}")
    else:
        key = prompt("   Enter your custom API key", required=False)
        if key:
            set_credential("MOTHER_API_KEY", key)
            print("   ✓ API key saved")
        else:
            print("   ⚠ Skipped - Mother will accept unauthenticated requests")


def setup_openai_key():
    """Set up optional OpenAI API key for memory features."""
    print("\n3. OPENAI API KEY (Optional)")
    print("   Enables semantic memory search via embeddings.")
    print()

    existing = read_credentials().get("OPENAI_API_KEY", "")
    if existing:
        print(f"   Current: {existing[:12]}...{existing[-4:]}")
        if not prompt_yes_no("   Update this key?", default=False):
            return

    if prompt_yes_no("   Set up OpenAI API key?", default=False):
        key = prompt_password("   Enter your OpenAI API key")
        set_credential("OPENAI_API_KEY", key)
        print("   ✓ OpenAI API key saved")
    else:
        print("   ⚠ Skipped - Memory features will use basic search")


def setup_email_prompt():
    """Ask about email setup."""
    print("\n4. EMAIL ACCOUNTS (Optional)")
    print("   Mother can manage your email via natural language.")
    print()

    if prompt_yes_no("   Set up email accounts now?", default=False):
        print("\n   Run: mother email add")
        print("   to configure IMAP/SMTP accounts interactively.")
    else:
        print("   ⚠ Skipped - You can run 'mother email add' later")


def show_summary():
    """Show configuration summary."""
    print("\n" + "=" * 60)
    print("SETUP COMPLETE")
    print("=" * 60)

    creds = read_credentials()

    print(f"\nCredentials file: {CREDENTIALS_FILE}")
    print("Permissions: 0o600 (owner read/write only)")
    print("\nConfigured credentials:")

    for key in sorted(creds.keys()):
        value = creds[key]
        masked = f"{value[:4]}...{value[-4:]}" if len(value) > 12 else "***"
        print(f"  • {key}: {masked}")

    print("\n" + "-" * 60)
    print("NEXT STEPS:")
    print("-" * 60)
    print("\n  1. Start the server:")
    print("     mother serve")
    print("\n  2. Check system status:")
    print("     mother status")
    print("\n  3. List available plugins:")
    print("     mother plugin list")
    print("\n  4. Add email accounts (optional):")
    print("     mother email add")
    print()


def run_setup(skip_optional: bool = False, quiet: bool = False) -> int:
    """Run the full setup wizard.

    Args:
        skip_optional: Skip optional configuration steps
        quiet: Minimal output

    Returns:
        Exit code (0 = success)
    """
    if not quiet:
        print_header()

    # Ensure config directory exists
    ensure_file_exists()

    # Required: Anthropic API key
    if not setup_anthropic_key():
        print("\n✗ Setup incomplete: Anthropic API key is required")
        return 1

    if not skip_optional:
        # Recommended: Mother API key
        setup_mother_api_key()

        # Optional: OpenAI for memory
        setup_openai_key()

        # Optional: Email setup
        setup_email_prompt()

    if not quiet:
        show_summary()

    return 0


def main(args: list[str] | None = None) -> int:
    """Main entry point for setup command."""
    if args is None:
        args = sys.argv[1:]

    skip_optional = "--quick" in args or "-q" in args
    quiet = "--quiet" in args

    if "--help" in args or "-h" in args:
        print("""
Mother Setup Wizard

Usage: mother setup [options]

Options:
  -q, --quick    Quick setup (only required settings)
  --quiet        Minimal output
  -h, --help     Show this help

The setup wizard will guide you through:
  1. Anthropic API key (required)
  2. Mother API key (recommended)
  3. OpenAI API key (optional, for memory)
  4. Email accounts (optional)
""")
        return 0

    try:
        return run_setup(skip_optional=skip_optional, quiet=quiet)
    except KeyboardInterrupt:
        print("\n\nSetup cancelled.")
        return 130
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
