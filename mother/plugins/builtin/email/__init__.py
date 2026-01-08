"""Built-in email plugin for Mother AI OS.

Provides email reading and sending capabilities via IMAP/SMTP.
"""

from __future__ import annotations

from typing import Any

from ....config.email_accounts import (
    get_account,
    get_default_account,
    list_accounts,
)
from ...base import PluginBase, PluginResult
from ...manifest import (
    CapabilitySpec,
    ExecutionSpec,
    ExecutionType,
    ParameterSpec,
    ParameterType,
    PluginManifest,
    PluginMetadata,
    PythonExecutionSpec,
)
from .imap_client import IMAPClient
from .smtp_client import EmailDraft, SMTPClient


def _create_manifest() -> PluginManifest:
    """Create the email plugin manifest programmatically."""
    return PluginManifest(
        schema_version="1.0",
        plugin=PluginMetadata(
            name="email",
            version="1.0.0",
            description="Email reading and sending for Mother AI OS via IMAP/SMTP",
            author="Mother",
            license="MIT",
        ),
        capabilities=[
            # List accounts
            CapabilitySpec(
                name="list_accounts",
                description="List all configured email accounts.",
                parameters=[],
            ),
            # List folders
            CapabilitySpec(
                name="list_folders",
                description="List all folders/mailboxes in an email account.",
                parameters=[
                    ParameterSpec(
                        name="account",
                        type=ParameterType.STRING,
                        description="Account name (uses default if not specified)",
                        required=False,
                    ),
                ],
            ),
            # List messages
            CapabilitySpec(
                name="list_messages",
                description="List email messages in a folder. Returns summaries without full body content.",
                parameters=[
                    ParameterSpec(
                        name="account",
                        type=ParameterType.STRING,
                        description="Account name (uses default if not specified)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="folder",
                        type=ParameterType.STRING,
                        description="Folder to list (default: INBOX)",
                        required=False,
                        default="INBOX",
                    ),
                    ParameterSpec(
                        name="limit",
                        type=ParameterType.INTEGER,
                        description="Maximum messages to return (default: 20)",
                        required=False,
                        default=20,
                    ),
                    ParameterSpec(
                        name="unread_only",
                        type=ParameterType.BOOLEAN,
                        description="Only return unread messages",
                        required=False,
                        default=False,
                    ),
                ],
            ),
            # Search messages
            CapabilitySpec(
                name="search_messages",
                description="Search for email messages matching criteria.",
                parameters=[
                    ParameterSpec(
                        name="account",
                        type=ParameterType.STRING,
                        description="Account name (uses default if not specified)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="query",
                        type=ParameterType.STRING,
                        description="Search query (e.g., 'FROM sender@example.com', 'SUBJECT invoice')",
                        required=True,
                    ),
                    ParameterSpec(
                        name="folder",
                        type=ParameterType.STRING,
                        description="Folder to search (default: INBOX)",
                        required=False,
                        default="INBOX",
                    ),
                    ParameterSpec(
                        name="limit",
                        type=ParameterType.INTEGER,
                        description="Maximum results (default: 20)",
                        required=False,
                        default=20,
                    ),
                ],
            ),
            # Read message
            CapabilitySpec(
                name="read_message",
                description="Read a specific email message by UID. Returns full content including body.",
                parameters=[
                    ParameterSpec(
                        name="uid",
                        type=ParameterType.STRING,
                        description="Message UID",
                        required=True,
                    ),
                    ParameterSpec(
                        name="account",
                        type=ParameterType.STRING,
                        description="Account name (uses default if not specified)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="folder",
                        type=ParameterType.STRING,
                        description="Folder containing the message (default: INBOX)",
                        required=False,
                        default="INBOX",
                    ),
                    ParameterSpec(
                        name="mark_read",
                        type=ParameterType.BOOLEAN,
                        description="Mark message as read after fetching",
                        required=False,
                        default=True,
                    ),
                ],
            ),
            # Send message
            CapabilitySpec(
                name="send_message",
                description="Send an email message.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="to",
                        type=ParameterType.STRING,
                        description="Recipient email address(es), comma-separated for multiple",
                        required=True,
                    ),
                    ParameterSpec(
                        name="subject",
                        type=ParameterType.STRING,
                        description="Email subject",
                        required=True,
                    ),
                    ParameterSpec(
                        name="body",
                        type=ParameterType.STRING,
                        description="Email body text",
                        required=True,
                    ),
                    ParameterSpec(
                        name="account",
                        type=ParameterType.STRING,
                        description="Account name to send from (uses default if not specified)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="cc",
                        type=ParameterType.STRING,
                        description="CC recipients, comma-separated",
                        required=False,
                    ),
                    ParameterSpec(
                        name="bcc",
                        type=ParameterType.STRING,
                        description="BCC recipients, comma-separated",
                        required=False,
                    ),
                    ParameterSpec(
                        name="html",
                        type=ParameterType.BOOLEAN,
                        description="Whether body is HTML (default: false)",
                        required=False,
                        default=False,
                    ),
                ],
            ),
            # Get unread count
            CapabilitySpec(
                name="unread_count",
                description="Get the count of unread messages in a folder.",
                parameters=[
                    ParameterSpec(
                        name="account",
                        type=ParameterType.STRING,
                        description="Account name (uses default if not specified)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="folder",
                        type=ParameterType.STRING,
                        description="Folder to check (default: INBOX)",
                        required=False,
                        default="INBOX",
                    ),
                ],
            ),
            # Mark as read/unread
            CapabilitySpec(
                name="mark_message",
                description="Mark a message as read or unread.",
                parameters=[
                    ParameterSpec(
                        name="uid",
                        type=ParameterType.STRING,
                        description="Message UID",
                        required=True,
                    ),
                    ParameterSpec(
                        name="read",
                        type=ParameterType.BOOLEAN,
                        description="True to mark as read, False for unread",
                        required=True,
                    ),
                    ParameterSpec(
                        name="account",
                        type=ParameterType.STRING,
                        description="Account name (uses default if not specified)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="folder",
                        type=ParameterType.STRING,
                        description="Folder containing the message (default: INBOX)",
                        required=False,
                        default="INBOX",
                    ),
                ],
            ),
            # Delete message
            CapabilitySpec(
                name="delete_message",
                description="Delete an email message.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="uid",
                        type=ParameterType.STRING,
                        description="Message UID",
                        required=True,
                    ),
                    ParameterSpec(
                        name="account",
                        type=ParameterType.STRING,
                        description="Account name (uses default if not specified)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="folder",
                        type=ParameterType.STRING,
                        description="Folder containing the message (default: INBOX)",
                        required=False,
                        default="INBOX",
                    ),
                ],
            ),
            # Move message
            CapabilitySpec(
                name="move_message",
                description="Move an email message to another folder.",
                parameters=[
                    ParameterSpec(
                        name="uid",
                        type=ParameterType.STRING,
                        description="Message UID",
                        required=True,
                    ),
                    ParameterSpec(
                        name="to_folder",
                        type=ParameterType.STRING,
                        description="Destination folder",
                        required=True,
                    ),
                    ParameterSpec(
                        name="account",
                        type=ParameterType.STRING,
                        description="Account name (uses default if not specified)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="from_folder",
                        type=ParameterType.STRING,
                        description="Source folder (default: INBOX)",
                        required=False,
                        default="INBOX",
                    ),
                ],
            ),
        ],
        execution=ExecutionSpec(
            type=ExecutionType.PYTHON,
            python=PythonExecutionSpec(
                module="mother.plugins.builtin.email",
                **{"class": "EmailPlugin"},
            ),
        ),
        permissions=[
            "email:read",
            "email:send",
            "email:delete",
        ],
    )


class EmailPlugin(PluginBase):
    """Built-in plugin for email operations via IMAP/SMTP."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the email plugin."""
        super().__init__(_create_manifest(), config)

    def _get_account(self, account_name: str | None) -> Any:
        """Get the specified account or default."""
        if account_name:
            account = get_account(account_name)
            if not account:
                raise ValueError(f"Email account not found: {account_name}")
            return account

        account = get_default_account()
        if not account:
            raise ValueError("No email accounts configured. Run: mother email add")
        return account

    async def execute(self, capability: str, params: dict[str, Any]) -> PluginResult:
        """Execute an email capability."""
        handlers = {
            "list_accounts": self._list_accounts,
            "list_folders": self._list_folders,
            "list_messages": self._list_messages,
            "search_messages": self._search_messages,
            "read_message": self._read_message,
            "send_message": self._send_message,
            "unread_count": self._unread_count,
            "mark_message": self._mark_message,
            "delete_message": self._delete_message,
            "move_message": self._move_message,
        }

        handler = handlers.get(capability)
        if not handler:
            return PluginResult.error_result(
                f"Unknown capability: {capability}",
                code="UNKNOWN_CAPABILITY",
            )

        try:
            return await handler(**params)
        except ValueError as e:
            return PluginResult.error_result(
                str(e),
                code="CONFIGURATION_ERROR",
            )
        except ConnectionRefusedError:
            return PluginResult.error_result(
                "Could not connect to email server",
                code="CONNECTION_REFUSED",
            )
        except Exception as e:
            return PluginResult.error_result(
                f"Email operation failed: {e}",
                code="EMAIL_ERROR",
            )

    async def _list_accounts(self) -> PluginResult:
        """List configured email accounts."""
        accounts = list_accounts()
        if not accounts:
            return PluginResult.error_result(
                "No email accounts configured. Run: mother email add",
                code="NOT_CONFIGURED",
            )

        account_list = []
        for acc in accounts:
            account_list.append(
                {
                    "name": acc.name,
                    "email": acc.email,
                    "display_name": acc.display_name,
                    "default": acc.default,
                    "has_imap": acc.imap is not None,
                    "has_smtp": acc.smtp is not None,
                }
            )

        return PluginResult.success_result(
            data={"accounts": account_list},
            message=f"Found {len(account_list)} email account(s)",
        )

    async def _list_folders(self, account: str | None = None) -> PluginResult:
        """List folders in an email account."""
        acc = self._get_account(account)

        with IMAPClient(acc) as client:
            folders = client.list_folders()

        return PluginResult.success_result(
            data={"folders": folders, "account": acc.name},
            message=f"Found {len(folders)} folder(s)",
        )

    async def _list_messages(
        self,
        account: str | None = None,
        folder: str = "INBOX",
        limit: int = 20,
        unread_only: bool = False,
    ) -> PluginResult:
        """List messages in a folder."""
        acc = self._get_account(account)
        criteria = "UNSEEN" if unread_only else "ALL"

        with IMAPClient(acc) as client:
            messages = client.fetch_messages(folder, criteria, limit)

        summaries = [msg.summary() for msg in messages]

        return PluginResult.success_result(
            data={
                "messages": summaries,
                "count": len(summaries),
                "folder": folder,
                "account": acc.name,
            },
            message=f"Found {len(summaries)} message(s) in {folder}",
        )

    async def _search_messages(
        self,
        query: str,
        account: str | None = None,
        folder: str = "INBOX",
        limit: int = 20,
    ) -> PluginResult:
        """Search for messages matching a query."""
        acc = self._get_account(account)

        with IMAPClient(acc) as client:
            messages = client.fetch_messages(folder, query, limit)

        summaries = [msg.summary() for msg in messages]

        return PluginResult.success_result(
            data={
                "messages": summaries,
                "count": len(summaries),
                "query": query,
                "folder": folder,
                "account": acc.name,
            },
            message=f"Found {len(summaries)} message(s) matching '{query}'",
        )

    async def _read_message(
        self,
        uid: str,
        account: str | None = None,
        folder: str = "INBOX",
        mark_read: bool = True,
    ) -> PluginResult:
        """Read a specific message."""
        acc = self._get_account(account)

        with IMAPClient(acc) as client:
            message = client.fetch_message(uid, folder)
            if mark_read:
                client.mark_read(uid, folder)

        return PluginResult.success_result(
            data={"message": message.to_dict()},
            message=f"Read message: {message.subject}",
        )

    async def _send_message(
        self,
        to: str,
        subject: str,
        body: str,
        account: str | None = None,
        cc: str | None = None,
        bcc: str | None = None,
        html: bool = False,
    ) -> PluginResult:
        """Send an email message."""
        acc = self._get_account(account)

        # Parse comma-separated recipients
        to_list = [r.strip() for r in to.split(",")]
        cc_list = [r.strip() for r in cc.split(",")] if cc else []
        bcc_list = [r.strip() for r in bcc.split(",")] if bcc else []

        draft = EmailDraft(
            to=to_list,
            subject=subject,
            body_text="" if html else body,
            body_html=body if html else "",
            cc=cc_list,
            bcc=bcc_list,
        )

        with SMTPClient(acc) as client:
            result = client.send(draft)

        return PluginResult.success_result(
            data=result,
            message=f"Email sent to {', '.join(to_list)}",
        )

    async def _unread_count(
        self,
        account: str | None = None,
        folder: str = "INBOX",
    ) -> PluginResult:
        """Get unread message count."""
        acc = self._get_account(account)

        with IMAPClient(acc) as client:
            count = client.get_unread_count(folder)

        return PluginResult.success_result(
            data={"unread": count, "folder": folder, "account": acc.name},
            message=f"{count} unread message(s) in {folder}",
        )

    async def _mark_message(
        self,
        uid: str,
        read: bool,
        account: str | None = None,
        folder: str = "INBOX",
    ) -> PluginResult:
        """Mark a message as read or unread."""
        acc = self._get_account(account)

        with IMAPClient(acc) as client:
            if read:
                success = client.mark_read(uid, folder)
            else:
                success = client.mark_unread(uid, folder)

        if success:
            status = "read" if read else "unread"
            return PluginResult.success_result(
                data={"uid": uid, "marked_as": status},
                message=f"Message marked as {status}",
            )
        else:
            return PluginResult.error_result(
                "Failed to update message status",
                code="UPDATE_FAILED",
            )

    async def _delete_message(
        self,
        uid: str,
        account: str | None = None,
        folder: str = "INBOX",
    ) -> PluginResult:
        """Delete a message."""
        acc = self._get_account(account)

        with IMAPClient(acc) as client:
            success = client.delete_message(uid, folder)

        if success:
            return PluginResult.success_result(
                data={"uid": uid, "deleted": True},
                message="Message deleted",
            )
        else:
            return PluginResult.error_result(
                "Failed to delete message",
                code="DELETE_FAILED",
            )

    async def _move_message(
        self,
        uid: str,
        to_folder: str,
        account: str | None = None,
        from_folder: str = "INBOX",
    ) -> PluginResult:
        """Move a message to another folder."""
        acc = self._get_account(account)

        with IMAPClient(acc) as client:
            success = client.move_message(uid, from_folder, to_folder)

        if success:
            return PluginResult.success_result(
                data={"uid": uid, "from": from_folder, "to": to_folder},
                message=f"Message moved to {to_folder}",
            )
        else:
            return PluginResult.error_result(
                "Failed to move message",
                code="MOVE_FAILED",
            )


__all__ = ["EmailPlugin"]
