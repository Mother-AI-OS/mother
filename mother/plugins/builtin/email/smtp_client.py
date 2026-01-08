"""SMTP client for email plugin.

Provides email sending capabilities via SMTP.
"""

from __future__ import annotations

import mimetypes
import smtplib
from dataclasses import dataclass, field
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

from ....config.email_accounts import EmailAccount, get_password


@dataclass
class EmailDraft:
    """Represents an email to be sent."""

    to: list[str]
    subject: str
    body_text: str = ""
    body_html: str = ""
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    attachments: list[Path] = field(default_factory=list)
    reply_to: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EmailDraft:
        """Create from dictionary."""
        to = data.get("to", [])
        if isinstance(to, str):
            to = [to]

        cc = data.get("cc", [])
        if isinstance(cc, str):
            cc = [cc]

        bcc = data.get("bcc", [])
        if isinstance(bcc, str):
            bcc = [bcc]

        attachments = data.get("attachments", [])
        if isinstance(attachments, str):
            attachments = [attachments]
        attachments = [Path(a) for a in attachments]

        return cls(
            to=to,
            subject=data.get("subject", ""),
            body_text=data.get("body_text", data.get("body", "")),
            body_html=data.get("body_html", ""),
            cc=cc,
            bcc=bcc,
            attachments=attachments,
            reply_to=data.get("reply_to", ""),
        )


class SMTPClient:
    """SMTP client for sending emails."""

    def __init__(self, account: EmailAccount):
        """Initialize SMTP client.

        Args:
            account: Email account configuration
        """
        self.account = account
        self._connection: smtplib.SMTP | smtplib.SMTP_SSL | None = None

    def connect(self) -> None:
        """Connect to the SMTP server."""
        if not self.account.smtp:
            raise ValueError(f"No SMTP config for account: {self.account.name}")

        password = get_password(self.account.name)
        if not password:
            raise ValueError(f"No password found for account: {self.account.name}")

        smtp = self.account.smtp
        if smtp.use_ssl:
            self._connection = smtplib.SMTP_SSL(smtp.host, smtp.port)
        else:
            self._connection = smtplib.SMTP(smtp.host, smtp.port)
            if smtp.use_starttls:
                self._connection.starttls()

        self._connection.login(self.account.email, password)

    def disconnect(self) -> None:
        """Disconnect from the server."""
        if self._connection:
            try:
                self._connection.quit()
            except Exception:
                pass
            self._connection = None

    def __enter__(self) -> SMTPClient:
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.disconnect()

    def _build_message(self, draft: EmailDraft) -> MIMEMultipart:
        """Build a MIME message from a draft."""
        # Create the root message
        if draft.attachments or draft.body_html:
            msg = MIMEMultipart("mixed")
        else:
            msg = MIMEMultipart()

        # Headers
        msg["From"] = (
            f"{self.account.display_name} <{self.account.email}>" if self.account.display_name else self.account.email
        )
        msg["To"] = ", ".join(draft.to)
        msg["Subject"] = draft.subject

        if draft.cc:
            msg["Cc"] = ", ".join(draft.cc)
        if draft.reply_to:
            msg["Reply-To"] = draft.reply_to

        # Body
        if draft.body_html and draft.body_text:
            # Both text and HTML - use alternative
            body_part = MIMEMultipart("alternative")
            body_part.attach(MIMEText(draft.body_text, "plain", "utf-8"))
            body_part.attach(MIMEText(draft.body_html, "html", "utf-8"))
            msg.attach(body_part)
        elif draft.body_html:
            msg.attach(MIMEText(draft.body_html, "html", "utf-8"))
        else:
            msg.attach(MIMEText(draft.body_text or "", "plain", "utf-8"))

        # Attachments
        for attachment_path in draft.attachments:
            if not attachment_path.exists():
                continue

            content_type, _ = mimetypes.guess_type(str(attachment_path))
            if content_type is None:
                content_type = "application/octet-stream"

            with open(attachment_path, "rb") as f:
                attachment = MIMEApplication(f.read())

            attachment.add_header(
                "Content-Disposition",
                "attachment",
                filename=attachment_path.name,
            )
            msg.attach(attachment)

        return msg

    def send(self, draft: EmailDraft) -> dict[str, Any]:
        """Send an email.

        Args:
            draft: Email draft to send

        Returns:
            Result dictionary with status
        """
        if not self._connection:
            raise ValueError("Not connected")

        if not draft.to:
            raise ValueError("No recipients specified")

        if not draft.subject:
            raise ValueError("No subject specified")

        msg = self._build_message(draft)

        # All recipients
        all_recipients = draft.to + draft.cc + draft.bcc

        # Send
        refused = self._connection.sendmail(
            self.account.email,
            all_recipients,
            msg.as_string(),
        )

        return {
            "sent": True,
            "from": self.account.email,
            "to": draft.to,
            "cc": draft.cc,
            "bcc": draft.bcc,
            "subject": draft.subject,
            "refused": list(refused.keys()) if refused else [],
        }

    def send_simple(
        self,
        to: str | list[str],
        subject: str,
        body: str,
        html: bool = False,
    ) -> dict[str, Any]:
        """Send a simple email.

        Args:
            to: Recipient(s)
            subject: Email subject
            body: Email body
            html: Whether body is HTML

        Returns:
            Result dictionary
        """
        if isinstance(to, str):
            to = [to]

        draft = EmailDraft(
            to=to,
            subject=subject,
            body_text="" if html else body,
            body_html=body if html else "",
        )

        return self.send(draft)


def send_email(
    account: EmailAccount,
    to: str | list[str],
    subject: str,
    body: str,
    html: bool = False,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    attachments: list[str | Path] | None = None,
) -> dict[str, Any]:
    """Convenience function to send an email.

    Args:
        account: Email account to send from
        to: Recipient(s)
        subject: Email subject
        body: Email body
        html: Whether body is HTML
        cc: CC recipients
        bcc: BCC recipients
        attachments: File paths to attach

    Returns:
        Result dictionary
    """
    if isinstance(to, str):
        to = [to]

    attachment_paths = []
    if attachments:
        attachment_paths = [Path(a) for a in attachments]

    draft = EmailDraft(
        to=to,
        subject=subject,
        body_text="" if html else body,
        body_html=body if html else "",
        cc=cc or [],
        bcc=bcc or [],
        attachments=attachment_paths,
    )

    with SMTPClient(account) as client:
        return client.send(draft)
