"""Built-in transmit plugin for Mother AI OS.

Provides document transmission capabilities via Email, Fax, Post, or beA.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

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
from .channels import get_channel, list_channels
from .storage import (
    Recipient,
    Transmission,
    TransmissionStatus,
    TransmissionStore,
)
from .storage import (
    TransmissionChannel as StorageChannel,
)


def _create_manifest() -> PluginManifest:
    """Create the transmit plugin manifest."""
    return PluginManifest(
        schema_version="1.0",
        plugin=PluginMetadata(
            name="transmit",
            version="1.0.0",
            description="Document transmission via Email, Fax, Post, or beA",
            author="Mother",
            license="MIT",
        ),
        capabilities=[
            # Send via email
            CapabilitySpec(
                name="email",
                description="Send document via email attachment.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="document",
                        type=ParameterType.STRING,
                        description="Path to PDF document to send",
                        required=True,
                    ),
                    ParameterSpec(
                        name="to",
                        type=ParameterType.STRING,
                        description="Recipient name",
                        required=True,
                    ),
                    ParameterSpec(
                        name="email",
                        type=ParameterType.STRING,
                        description="Recipient email address",
                        required=True,
                    ),
                    ParameterSpec(
                        name="subject",
                        type=ParameterType.STRING,
                        description="Email subject line",
                        required=False,
                    ),
                    ParameterSpec(
                        name="cover",
                        type=ParameterType.STRING,
                        description="Cover letter / email body text",
                        required=False,
                    ),
                    ParameterSpec(
                        name="reference",
                        type=ParameterType.STRING,
                        description="Case reference (Aktenzeichen)",
                        required=False,
                    ),
                ],
            ),
            # Send via fax
            CapabilitySpec(
                name="fax",
                description="Send document via fax (simple-fax.de).",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="document",
                        type=ParameterType.STRING,
                        description="Path to PDF document to send",
                        required=True,
                    ),
                    ParameterSpec(
                        name="to",
                        type=ParameterType.STRING,
                        description="Recipient name",
                        required=True,
                    ),
                    ParameterSpec(
                        name="fax",
                        type=ParameterType.STRING,
                        description="Recipient fax number (e.g., +49 221 12345678)",
                        required=True,
                    ),
                    ParameterSpec(
                        name="subject",
                        type=ParameterType.STRING,
                        description="Fax subject/header",
                        required=False,
                    ),
                    ParameterSpec(
                        name="cover",
                        type=ParameterType.STRING,
                        description="Cover page text",
                        required=False,
                    ),
                    ParameterSpec(
                        name="reference",
                        type=ParameterType.STRING,
                        description="Case reference (Aktenzeichen)",
                        required=False,
                    ),
                ],
            ),
            # Send via post
            CapabilitySpec(
                name="post",
                description="Send document via postal mail (LetterXpress).",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="document",
                        type=ParameterType.STRING,
                        description="Path to PDF document to send",
                        required=True,
                    ),
                    ParameterSpec(
                        name="to",
                        type=ParameterType.STRING,
                        description="Recipient name",
                        required=True,
                    ),
                    ParameterSpec(
                        name="street",
                        type=ParameterType.STRING,
                        description="Street address",
                        required=True,
                    ),
                    ParameterSpec(
                        name="plz",
                        type=ParameterType.STRING,
                        description="Postal code (PLZ)",
                        required=True,
                    ),
                    ParameterSpec(
                        name="city",
                        type=ParameterType.STRING,
                        description="City",
                        required=True,
                    ),
                    ParameterSpec(
                        name="country",
                        type=ParameterType.STRING,
                        description="Country code (default: DE)",
                        required=False,
                        default="DE",
                    ),
                    ParameterSpec(
                        name="reference",
                        type=ParameterType.STRING,
                        description="Case reference (Aktenzeichen)",
                        required=False,
                    ),
                ],
            ),
            # Send via beA
            CapabilitySpec(
                name="bea",
                description="Send document via beA (German lawyer mailbox).",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="document",
                        type=ParameterType.STRING,
                        description="Path to PDF document to send",
                        required=True,
                    ),
                    ParameterSpec(
                        name="to",
                        type=ParameterType.STRING,
                        description="Recipient name (court or lawyer)",
                        required=True,
                    ),
                    ParameterSpec(
                        name="safe_id",
                        type=ParameterType.STRING,
                        description="Recipient SAFE-ID (e.g., DE.BRAK.12345)",
                        required=True,
                    ),
                    ParameterSpec(
                        name="subject",
                        type=ParameterType.STRING,
                        description="Message subject",
                        required=False,
                    ),
                    ParameterSpec(
                        name="reference",
                        type=ParameterType.STRING,
                        description="Case reference / Aktenzeichen (required for beA)",
                        required=True,
                    ),
                ],
            ),
            # List channels
            CapabilitySpec(
                name="channels",
                description="List available transmission channels and their configuration status.",
                parameters=[],
            ),
            # Get transmission history
            CapabilitySpec(
                name="history",
                description="Show transmission history.",
                parameters=[
                    ParameterSpec(
                        name="channel",
                        type=ParameterType.STRING,
                        description="Filter by channel (email, fax, post, bea)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="status",
                        type=ParameterType.STRING,
                        description="Filter by status (pending, sent, delivered, failed)",
                        required=False,
                    ),
                    ParameterSpec(
                        name="reference",
                        type=ParameterType.STRING,
                        description="Filter by case reference",
                        required=False,
                    ),
                    ParameterSpec(
                        name="limit",
                        type=ParameterType.INTEGER,
                        description="Number of entries to show (default: 20)",
                        required=False,
                        default=20,
                    ),
                ],
            ),
            # Get specific transmission
            CapabilitySpec(
                name="get",
                description="Get details of a specific transmission.",
                parameters=[
                    ParameterSpec(
                        name="transmission_id",
                        type=ParameterType.STRING,
                        description="Transmission ID",
                        required=True,
                    ),
                ],
            ),
            # Get stats
            CapabilitySpec(
                name="stats",
                description="Get transmission statistics.",
                parameters=[],
            ),
        ],
        execution=ExecutionSpec(
            type=ExecutionType.PYTHON,
            python=PythonExecutionSpec(
                module="mother.plugins.builtin.transmit",
                **{"class": "TransmitPlugin"},
            ),
        ),
        permissions=[
            "filesystem:read",
            "network:smtp",
            "network:https",
        ],
    )


class TransmitPlugin(PluginBase):
    """Built-in plugin for document transmission."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the transmit plugin."""
        super().__init__(_create_manifest(), config)

        # Initialize storage
        db_path = None
        if config and "db_path" in config:
            db_path = Path(config["db_path"])
        self._store = TransmissionStore(db_path)

        # Channel configuration
        self._channel_config = config or {}

    async def execute(self, capability: str, params: dict[str, Any]) -> PluginResult:
        """Execute a transmit capability."""
        handlers = {
            "email": self._send_email,
            "fax": self._send_fax,
            "post": self._send_post,
            "bea": self._send_bea,
            "channels": self._channels,
            "history": self._history,
            "get": self._get,
            "stats": self._stats,
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
                code="INVALID_INPUT",
            )
        except Exception as e:
            return PluginResult.error_result(
                f"Transmission failed: {e}",
                code="TRANSMISSION_ERROR",
            )

    async def _send_email(
        self,
        document: str,
        to: str,
        email: str,
        subject: str = "",
        cover: str = "",
        reference: str = "",
    ) -> PluginResult:
        """Send document via email."""
        # Validate document exists
        doc_path = Path(document)
        if not doc_path.exists():
            return PluginResult.error_result(
                f"Document not found: {document}",
                code="FILE_NOT_FOUND",
            )

        # Create recipient
        recipient = Recipient(name=to, email=email)

        # Create transmission record
        transmission = Transmission(
            transmission_id=self._store.generate_id(),
            channel=StorageChannel.EMAIL,
            status=TransmissionStatus.PENDING,
            document_path=str(doc_path.absolute()),
            recipient=recipient,
            subject=subject,
            cover_text=cover,
            reference=reference,
        )

        # Store pending transmission
        self._store.add_transmission(transmission)

        # Get channel and send
        channel = get_channel("email")
        if not channel:
            return PluginResult.error_result(
                "Email channel not available",
                code="CHANNEL_ERROR",
            )

        result = await channel.send(transmission, self._channel_config)

        if result.success:
            self._store.update_status(
                transmission.transmission_id,
                TransmissionStatus.SENT,
            )
            return PluginResult.success_result(
                data={
                    "transmission_id": transmission.transmission_id,
                    "channel": "email",
                    "status": "sent",
                    "recipient": email,
                    "document": doc_path.name,
                },
                message=result.message,
            )
        else:
            self._store.update_status(
                transmission.transmission_id,
                TransmissionStatus.FAILED,
                error_message=result.error,
            )
            return PluginResult.error_result(
                result.error,
                code="SEND_FAILED",
            )

    async def _send_fax(
        self,
        document: str,
        to: str,
        fax: str,
        subject: str = "",
        cover: str = "",
        reference: str = "",
    ) -> PluginResult:
        """Send document via fax."""
        doc_path = Path(document)
        if not doc_path.exists():
            return PluginResult.error_result(
                f"Document not found: {document}",
                code="FILE_NOT_FOUND",
            )

        recipient = Recipient(name=to, fax=fax)

        transmission = Transmission(
            transmission_id=self._store.generate_id(),
            channel=StorageChannel.FAX,
            status=TransmissionStatus.PENDING,
            document_path=str(doc_path.absolute()),
            recipient=recipient,
            subject=subject,
            cover_text=cover,
            reference=reference,
        )

        self._store.add_transmission(transmission)

        channel = get_channel("fax")
        if not channel:
            return PluginResult.error_result(
                "Fax channel not available",
                code="CHANNEL_ERROR",
            )

        result = await channel.send(transmission, self._channel_config)

        if result.success:
            self._store.update_status(
                transmission.transmission_id,
                TransmissionStatus.SENT,
            )
            return PluginResult.success_result(
                data={
                    "transmission_id": transmission.transmission_id,
                    "channel": "fax",
                    "status": "sent",
                    "recipient": fax,
                    "document": doc_path.name,
                },
                message=result.message,
            )
        else:
            self._store.update_status(
                transmission.transmission_id,
                TransmissionStatus.FAILED,
                error_message=result.error,
            )
            return PluginResult.error_result(
                result.error,
                code="NOT_CONFIGURED",
            )

    async def _send_post(
        self,
        document: str,
        to: str,
        street: str,
        plz: str,
        city: str,
        country: str = "DE",
        reference: str = "",
    ) -> PluginResult:
        """Send document via postal mail."""
        doc_path = Path(document)
        if not doc_path.exists():
            return PluginResult.error_result(
                f"Document not found: {document}",
                code="FILE_NOT_FOUND",
            )

        recipient = Recipient(
            name=to,
            street=street,
            plz=plz,
            city=city,
            country=country,
        )

        transmission = Transmission(
            transmission_id=self._store.generate_id(),
            channel=StorageChannel.POST,
            status=TransmissionStatus.PENDING,
            document_path=str(doc_path.absolute()),
            recipient=recipient,
            reference=reference,
        )

        self._store.add_transmission(transmission)

        channel = get_channel("post")
        if not channel:
            return PluginResult.error_result(
                "Postal channel not available",
                code="CHANNEL_ERROR",
            )

        result = await channel.send(transmission, self._channel_config)

        if result.success:
            self._store.update_status(
                transmission.transmission_id,
                TransmissionStatus.SENT,
            )
            return PluginResult.success_result(
                data={
                    "transmission_id": transmission.transmission_id,
                    "channel": "post",
                    "status": "sent",
                    "recipient": f"{to}, {street}, {plz} {city}",
                    "document": doc_path.name,
                },
                message=result.message,
            )
        else:
            self._store.update_status(
                transmission.transmission_id,
                TransmissionStatus.FAILED,
                error_message=result.error,
            )
            return PluginResult.error_result(
                result.error,
                code="NOT_CONFIGURED",
            )

    async def _send_bea(
        self,
        document: str,
        to: str,
        safe_id: str,
        reference: str,
        subject: str = "",
    ) -> PluginResult:
        """Send document via beA."""
        doc_path = Path(document)
        if not doc_path.exists():
            return PluginResult.error_result(
                f"Document not found: {document}",
                code="FILE_NOT_FOUND",
            )

        recipient = Recipient(name=to, safe_id=safe_id)

        transmission = Transmission(
            transmission_id=self._store.generate_id(),
            channel=StorageChannel.BEA,
            status=TransmissionStatus.PENDING,
            document_path=str(doc_path.absolute()),
            recipient=recipient,
            subject=subject,
            reference=reference,
        )

        self._store.add_transmission(transmission)

        channel = get_channel("bea")
        if not channel:
            return PluginResult.error_result(
                "beA channel not available",
                code="CHANNEL_ERROR",
            )

        result = await channel.send(transmission, self._channel_config)

        if result.success:
            self._store.update_status(
                transmission.transmission_id,
                TransmissionStatus.SENT,
            )
            return PluginResult.success_result(
                data={
                    "transmission_id": transmission.transmission_id,
                    "channel": "bea",
                    "status": "sent",
                    "recipient": f"{to} ({safe_id})",
                    "reference": reference,
                    "document": doc_path.name,
                },
                message=result.message,
            )
        else:
            self._store.update_status(
                transmission.transmission_id,
                TransmissionStatus.FAILED,
                error_message=result.error,
            )
            return PluginResult.error_result(
                result.error,
                code="NOT_CONFIGURED",
            )

    async def _channels(self) -> PluginResult:
        """List available channels and configuration status."""
        channels_info = []

        for channel_info in list_channels():
            channel = get_channel(channel_info["name"])
            if channel:
                configured = channel.is_configured(self._channel_config)
                channels_info.append({
                    "name": channel_info["name"],
                    "configured": configured,
                    "requires": channel_info["requires_config"],
                })

        return PluginResult.success_result(
            data={"channels": channels_info},
            message=f"Found {len(channels_info)} transmission channels",
        )

    async def _history(
        self,
        channel: str | None = None,
        status: str | None = None,
        reference: str | None = None,
        limit: int = 20,
    ) -> PluginResult:
        """Get transmission history."""
        # Parse channel filter
        channel_filter = None
        if channel:
            try:
                channel_filter = StorageChannel(channel.lower())
            except ValueError:
                return PluginResult.error_result(
                    f"Invalid channel: {channel}",
                    code="INVALID_INPUT",
                )

        # Parse status filter
        status_filter = None
        if status:
            try:
                status_filter = TransmissionStatus(status.lower())
            except ValueError:
                return PluginResult.error_result(
                    f"Invalid status: {status}",
                    code="INVALID_INPUT",
                )

        transmissions = self._store.list_transmissions(
            channel=channel_filter,
            status=status_filter,
            reference=reference,
            limit=limit,
        )

        return PluginResult.success_result(
            data={
                "transmissions": [t.summary() for t in transmissions],
                "count": len(transmissions),
            },
            message=f"Found {len(transmissions)} transmission(s)",
        )

    async def _get(self, transmission_id: str) -> PluginResult:
        """Get transmission details."""
        transmission = self._store.get_transmission(transmission_id)

        if not transmission:
            return PluginResult.error_result(
                f"Transmission not found: {transmission_id}",
                code="NOT_FOUND",
            )

        return PluginResult.success_result(
            data=transmission.to_dict(),
            message=f"Transmission {transmission_id}",
        )

    async def _stats(self) -> PluginResult:
        """Get transmission statistics."""
        stats = self._store.get_stats()

        return PluginResult.success_result(
            data=stats,
            message=f"Total: {stats['total']} transmissions",
        )


__all__ = ["TransmitPlugin"]
