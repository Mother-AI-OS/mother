"""Transmission channel implementations."""

from __future__ import annotations

import smtplib
from abc import ABC, abstractmethod
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .storage import Transmission


class ChannelResult:
    """Result of a transmission attempt."""

    def __init__(
        self,
        success: bool,
        message: str = "",
        error: str = "",
        metadata: dict[str, Any] | None = None,
    ):
        self.success = success
        self.message = message
        self.error = error
        self.metadata = metadata or {}


class TransmissionChannel(ABC):
    """Base class for transmission channels."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Channel name."""
        pass

    @property
    @abstractmethod
    def requires_config(self) -> list[str]:
        """List of required configuration keys."""
        pass

    @abstractmethod
    def is_configured(self, config: dict[str, Any]) -> bool:
        """Check if channel is properly configured."""
        pass

    @abstractmethod
    async def send(
        self,
        transmission: Transmission,
        config: dict[str, Any],
    ) -> ChannelResult:
        """Send a transmission.

        Args:
            transmission: The transmission to send
            config: Channel configuration

        Returns:
            Result of the transmission attempt
        """
        pass


class EmailChannel(TransmissionChannel):
    """Email transmission channel.

    Uses SMTP to send documents as email attachments.
    """

    @property
    def name(self) -> str:
        return "email"

    @property
    def requires_config(self) -> list[str]:
        return ["smtp_host", "smtp_port", "smtp_user", "smtp_password", "from_email"]

    def is_configured(self, config: dict[str, Any]) -> bool:
        """Check if email is configured."""
        return all(config.get(key) for key in self.requires_config)

    async def send(
        self,
        transmission: Transmission,
        config: dict[str, Any],
    ) -> ChannelResult:
        """Send document via email."""
        if not transmission.recipient.email:
            return ChannelResult(
                success=False,
                error="Recipient email address not provided",
            )

        doc_path = Path(transmission.document_path)
        if not doc_path.exists():
            return ChannelResult(
                success=False,
                error=f"Document not found: {transmission.document_path}",
            )

        try:
            # Create message
            msg = MIMEMultipart()
            msg["From"] = config.get("from_email", config.get("smtp_user", ""))
            msg["To"] = transmission.recipient.email
            msg["Subject"] = transmission.subject or f"Document: {doc_path.name}"

            # Add cover text as body
            body = transmission.cover_text or f"Please find attached: {doc_path.name}"
            if transmission.reference:
                body = f"Re: {transmission.reference}\n\n{body}"
            msg.attach(MIMEText(body, "plain"))

            # Attach document
            with open(doc_path, "rb") as f:
                attachment = MIMEApplication(f.read(), _subtype="pdf")
                attachment.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=doc_path.name,
                )
                msg.attach(attachment)

            # Send via SMTP
            smtp_host = config.get("smtp_host", "")
            smtp_port = int(config.get("smtp_port", 465))
            use_ssl = config.get("smtp_ssl", True)

            if use_ssl:
                with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
                    server.login(
                        config.get("smtp_user", ""),
                        config.get("smtp_password", ""),
                    )
                    server.send_message(msg)
            else:
                with smtplib.SMTP(smtp_host, smtp_port) as server:
                    server.starttls()
                    server.login(
                        config.get("smtp_user", ""),
                        config.get("smtp_password", ""),
                    )
                    server.send_message(msg)

            return ChannelResult(
                success=True,
                message=f"Email sent to {transmission.recipient.email}",
                metadata={"recipient_email": transmission.recipient.email},
            )

        except smtplib.SMTPAuthenticationError as e:
            return ChannelResult(
                success=False,
                error=f"SMTP authentication failed: {e}",
            )
        except smtplib.SMTPException as e:
            return ChannelResult(
                success=False,
                error=f"SMTP error: {e}",
            )
        except Exception as e:
            return ChannelResult(
                success=False,
                error=f"Failed to send email: {e}",
            )


class FaxChannel(TransmissionChannel):
    """Fax transmission channel.

    Uses simple-fax.de API to send faxes.
    """

    @property
    def name(self) -> str:
        return "fax"

    @property
    def requires_config(self) -> list[str]:
        return ["simplefax_user", "simplefax_password"]

    def is_configured(self, config: dict[str, Any]) -> bool:
        """Check if fax is configured."""
        return all(config.get(key) for key in self.requires_config)

    async def send(
        self,
        transmission: Transmission,
        config: dict[str, Any],
    ) -> ChannelResult:
        """Send document via fax."""
        if not transmission.recipient.fax:
            return ChannelResult(
                success=False,
                error="Recipient fax number not provided",
            )

        doc_path = Path(transmission.document_path)
        if not doc_path.exists():
            return ChannelResult(
                success=False,
                error=f"Document not found: {transmission.document_path}",
            )

        # Check configuration
        if not self.is_configured(config):
            return ChannelResult(
                success=False,
                error="Fax channel not configured. Set simplefax_user and simplefax_password.",
            )

        # TODO: Implement simple-fax.de API integration
        # For now, return not implemented
        return ChannelResult(
            success=False,
            error="Fax transmission not yet implemented. Configure simple-fax.de credentials.",
        )


class PostChannel(TransmissionChannel):
    """Postal mail transmission channel.

    Uses LetterXpress API to send physical letters.
    """

    @property
    def name(self) -> str:
        return "post"

    @property
    def requires_config(self) -> list[str]:
        return ["letterxpress_user", "letterxpress_api_key"]

    def is_configured(self, config: dict[str, Any]) -> bool:
        """Check if post is configured."""
        return all(config.get(key) for key in self.requires_config)

    async def send(
        self,
        transmission: Transmission,
        config: dict[str, Any],
    ) -> ChannelResult:
        """Send document via postal mail."""
        recipient = transmission.recipient

        # Validate address
        if not all([recipient.street, recipient.plz, recipient.city]):
            return ChannelResult(
                success=False,
                error="Incomplete postal address: street, plz, and city required",
            )

        doc_path = Path(transmission.document_path)
        if not doc_path.exists():
            return ChannelResult(
                success=False,
                error=f"Document not found: {transmission.document_path}",
            )

        # Check configuration
        if not self.is_configured(config):
            return ChannelResult(
                success=False,
                error="Postal channel not configured. Set letterxpress_user and letterxpress_api_key.",
            )

        # TODO: Implement LetterXpress API integration
        return ChannelResult(
            success=False,
            error="Postal transmission not yet implemented. Configure LetterXpress credentials.",
        )


class BeAChannel(TransmissionChannel):
    """beA (besonderes elektronisches Anwaltspostfach) transmission channel.

    German lawyer electronic mailbox for court communications.
    """

    @property
    def name(self) -> str:
        return "bea"

    @property
    def requires_config(self) -> list[str]:
        return ["bea_safe_id", "bea_certificate_path", "bea_pin"]

    def is_configured(self, config: dict[str, Any]) -> bool:
        """Check if beA is configured."""
        return all(config.get(key) for key in self.requires_config)

    async def send(
        self,
        transmission: Transmission,
        config: dict[str, Any],
    ) -> ChannelResult:
        """Send document via beA."""
        if not transmission.recipient.safe_id:
            return ChannelResult(
                success=False,
                error="Recipient SAFE-ID not provided",
            )

        if not transmission.reference:
            return ChannelResult(
                success=False,
                error="Case reference (Aktenzeichen) is required for beA transmissions",
            )

        doc_path = Path(transmission.document_path)
        if not doc_path.exists():
            return ChannelResult(
                success=False,
                error=f"Document not found: {transmission.document_path}",
            )

        # Check configuration
        if not self.is_configured(config):
            return ChannelResult(
                success=False,
                error="beA channel not configured. Set bea_safe_id, bea_certificate_path, and bea_pin.",
            )

        # TODO: Implement beA EGVP integration
        return ChannelResult(
            success=False,
            error="beA transmission not yet implemented. Configure beA credentials.",
        )


# Channel registry
CHANNELS: dict[str, type[TransmissionChannel]] = {
    "email": EmailChannel,
    "fax": FaxChannel,
    "post": PostChannel,
    "bea": BeAChannel,
}


def get_channel(name: str) -> TransmissionChannel | None:
    """Get a channel instance by name."""
    channel_class = CHANNELS.get(name)
    if channel_class:
        return channel_class()
    return None


def list_channels() -> list[dict[str, Any]]:
    """List all available channels with their configuration requirements."""
    result = []
    for name, channel_class in CHANNELS.items():
        channel = channel_class()
        result.append(
            {
                "name": name,
                "requires_config": channel.requires_config,
            }
        )
    return result
