"""Tests for the built-in transmit plugin."""

import pytest

from mother.plugins.builtin.transmit import TransmitPlugin
from mother.plugins.builtin.transmit.channels import (
    BeAChannel,
    ChannelResult,
    EmailChannel,
    FaxChannel,
    PostChannel,
    get_channel,
    list_channels,
)
from mother.plugins.builtin.transmit.storage import (
    Recipient,
    Transmission,
    TransmissionChannel,
    TransmissionStatus,
    TransmissionStore,
)


class TestRecipient:
    """Tests for Recipient dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        recipient = Recipient(
            name="John Doe",
            email="john@example.com",
            fax="+49 221 12345678",
        )
        data = recipient.to_dict()
        assert data["name"] == "John Doe"
        assert data["email"] == "john@example.com"
        assert data["fax"] == "+49 221 12345678"
        assert data["country"] == "DE"

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "street": "Main St 1",
            "plz": "50858",
            "city": "Cologne",
        }
        recipient = Recipient.from_dict(data)
        assert recipient.name == "Jane Doe"
        assert recipient.email == "jane@example.com"
        assert recipient.street == "Main St 1"
        assert recipient.plz == "50858"
        assert recipient.city == "Cologne"


class TestTransmission:
    """Tests for Transmission dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        recipient = Recipient(name="Test", email="test@example.com")
        transmission = Transmission(
            transmission_id="abc123",
            channel=TransmissionChannel.EMAIL,
            status=TransmissionStatus.PENDING,
            document_path="/path/to/doc.pdf",
            recipient=recipient,
            subject="Test Subject",
            reference="123/24",
        )
        data = transmission.to_dict()
        assert data["transmission_id"] == "abc123"
        assert data["channel"] == "email"
        assert data["status"] == "pending"
        assert data["document_path"] == "/path/to/doc.pdf"
        assert data["subject"] == "Test Subject"
        assert data["reference"] == "123/24"

    def test_summary(self):
        """Test summary output."""
        recipient = Recipient(name="Test User")
        transmission = Transmission(
            transmission_id="xyz789",
            channel=TransmissionChannel.FAX,
            status=TransmissionStatus.SENT,
            document_path="/doc.pdf",
            recipient=recipient,
            subject="Fax Test",
        )
        summary = transmission.summary()
        assert summary["transmission_id"] == "xyz789"
        assert summary["channel"] == "fax"
        assert summary["status"] == "sent"
        assert summary["recipient"] == "Test User"


class TestTransmissionStore:
    """Tests for TransmissionStore."""

    @pytest.fixture
    def store(self, tmp_path):
        """Create a temporary transmission store."""
        return TransmissionStore(tmp_path / "transmit.db")

    @pytest.fixture
    def sample_transmission(self, store):
        """Create a sample transmission."""
        recipient = Recipient(name="Test", email="test@example.com")
        transmission = Transmission(
            transmission_id=store.generate_id(),
            channel=TransmissionChannel.EMAIL,
            status=TransmissionStatus.PENDING,
            document_path="/doc.pdf",
            recipient=recipient,
            subject="Test",
            reference="REF-001",
        )
        store.add_transmission(transmission)
        return transmission

    def test_add_and_get_transmission(self, store):
        """Test adding and retrieving a transmission."""
        recipient = Recipient(name="John", email="john@test.com")
        transmission = Transmission(
            transmission_id=store.generate_id(),
            channel=TransmissionChannel.EMAIL,
            status=TransmissionStatus.PENDING,
            document_path="/path/doc.pdf",
            recipient=recipient,
            subject="Test Email",
        )
        tid = store.add_transmission(transmission)

        retrieved = store.get_transmission(tid)
        assert retrieved is not None
        assert retrieved.subject == "Test Email"
        assert retrieved.recipient.email == "john@test.com"

    def test_update_status_to_sent(self, store, sample_transmission):
        """Test updating status to sent."""
        success = store.update_status(
            sample_transmission.transmission_id,
            TransmissionStatus.SENT,
        )
        assert success is True

        retrieved = store.get_transmission(sample_transmission.transmission_id)
        assert retrieved.status == TransmissionStatus.SENT
        assert retrieved.sent_at is not None

    def test_update_status_to_failed(self, store, sample_transmission):
        """Test updating status to failed with error."""
        success = store.update_status(
            sample_transmission.transmission_id,
            TransmissionStatus.FAILED,
            error_message="Connection timeout",
        )
        assert success is True

        retrieved = store.get_transmission(sample_transmission.transmission_id)
        assert retrieved.status == TransmissionStatus.FAILED
        assert retrieved.error_message == "Connection timeout"

    def test_list_transmissions(self, store):
        """Test listing transmissions."""
        recipient = Recipient(name="Test")
        for i in range(5):
            t = Transmission(
                transmission_id=store.generate_id(),
                channel=TransmissionChannel.EMAIL,
                status=TransmissionStatus.PENDING,
                document_path=f"/doc{i}.pdf",
                recipient=recipient,
            )
            store.add_transmission(t)

        results = store.list_transmissions()
        assert len(results) == 5

    def test_list_by_channel(self, store, sample_transmission):
        """Test filtering by channel."""
        recipient = Recipient(name="Test", fax="+49 123")
        fax_t = Transmission(
            transmission_id=store.generate_id(),
            channel=TransmissionChannel.FAX,
            status=TransmissionStatus.PENDING,
            document_path="/fax.pdf",
            recipient=recipient,
        )
        store.add_transmission(fax_t)

        email_results = store.list_transmissions(channel=TransmissionChannel.EMAIL)
        assert len(email_results) == 1
        assert email_results[0].channel == TransmissionChannel.EMAIL

        fax_results = store.list_transmissions(channel=TransmissionChannel.FAX)
        assert len(fax_results) == 1
        assert fax_results[0].channel == TransmissionChannel.FAX

    def test_list_by_status(self, store, sample_transmission):
        """Test filtering by status."""
        store.update_status(
            sample_transmission.transmission_id,
            TransmissionStatus.SENT,
        )

        pending = store.list_transmissions(status=TransmissionStatus.PENDING)
        assert len(pending) == 0

        sent = store.list_transmissions(status=TransmissionStatus.SENT)
        assert len(sent) == 1

    def test_list_by_reference(self, store, sample_transmission):
        """Test filtering by reference."""
        results = store.list_transmissions(reference="REF-001")
        assert len(results) == 1
        assert results[0].reference == "REF-001"

        no_results = store.list_transmissions(reference="NONEXISTENT")
        assert len(no_results) == 0

    def test_get_stats(self, store, sample_transmission):
        """Test getting statistics."""
        stats = store.get_stats()
        assert stats["total"] == 1
        assert "by_channel" in stats
        assert "by_status" in stats


class TestChannels:
    """Tests for transmission channels."""

    def test_list_channels(self):
        """Test listing available channels."""
        channels = list_channels()
        assert len(channels) == 4
        channel_names = [c["name"] for c in channels]
        assert "email" in channel_names
        assert "fax" in channel_names
        assert "post" in channel_names
        assert "bea" in channel_names

    def test_get_channel(self):
        """Test getting channel by name."""
        email = get_channel("email")
        assert email is not None
        assert email.name == "email"

        fax = get_channel("fax")
        assert fax is not None
        assert fax.name == "fax"

        unknown = get_channel("unknown")
        assert unknown is None

    def test_email_channel_not_configured(self):
        """Test email channel without config."""
        channel = EmailChannel()
        assert channel.is_configured({}) is False
        assert channel.is_configured({"smtp_host": "mail.example.com"}) is False

    def test_email_channel_configured(self):
        """Test email channel with config."""
        channel = EmailChannel()
        config = {
            "smtp_host": "smtp.example.com",
            "smtp_port": 465,
            "smtp_user": "user@example.com",
            "smtp_password": "secret",
            "from_email": "user@example.com",
        }
        assert channel.is_configured(config) is True

    def test_fax_channel_requires_config(self):
        """Test fax channel config requirements."""
        channel = FaxChannel()
        assert "simplefax_user" in channel.requires_config
        assert "simplefax_password" in channel.requires_config

    def test_post_channel_requires_config(self):
        """Test post channel config requirements."""
        channel = PostChannel()
        assert "letterxpress_user" in channel.requires_config
        assert "letterxpress_api_key" in channel.requires_config

    def test_bea_channel_requires_config(self):
        """Test beA channel config requirements."""
        channel = BeAChannel()
        assert "bea_safe_id" in channel.requires_config
        assert "bea_certificate_path" in channel.requires_config
        assert "bea_pin" in channel.requires_config


class TestTransmitPlugin:
    """Tests for TransmitPlugin."""

    @pytest.fixture
    def plugin(self, tmp_path):
        """Create a plugin with temporary storage."""
        return TransmitPlugin(config={"db_path": str(tmp_path / "transmit.db")})

    @pytest.fixture
    def test_document(self, tmp_path):
        """Create a test document."""
        doc = tmp_path / "test.pdf"
        doc.write_bytes(b"%PDF-1.4 test")
        return str(doc)

    def test_init(self, plugin):
        """Test plugin initialization."""
        assert plugin.manifest.plugin.name == "transmit"
        assert plugin.manifest.plugin.version == "1.0.0"

    def test_capabilities(self, plugin):
        """Test plugin capabilities."""
        caps = plugin.get_capabilities()
        assert len(caps) == 8
        cap_names = [c.name for c in caps]
        assert "email" in cap_names
        assert "fax" in cap_names
        assert "post" in cap_names
        assert "bea" in cap_names
        assert "channels" in cap_names
        assert "history" in cap_names
        assert "get" in cap_names
        assert "stats" in cap_names

    def test_send_requires_confirmation(self, plugin):
        """Test send operations require confirmation."""
        caps = plugin.get_capabilities()
        email_cap = next(c for c in caps if c.name == "email")
        assert email_cap.confirmation_required is True

        fax_cap = next(c for c in caps if c.name == "fax")
        assert fax_cap.confirmation_required is True

        post_cap = next(c for c in caps if c.name == "post")
        assert post_cap.confirmation_required is True

        bea_cap = next(c for c in caps if c.name == "bea")
        assert bea_cap.confirmation_required is True

    @pytest.mark.asyncio
    async def test_unknown_capability(self, plugin):
        """Test unknown capability."""
        result = await plugin.execute("unknown", {})
        assert result.success is False
        assert result.error_code == "UNKNOWN_CAPABILITY"

    @pytest.mark.asyncio
    async def test_email_document_not_found(self, plugin):
        """Test email with non-existent document."""
        result = await plugin.execute(
            "email",
            {
                "document": "/nonexistent/doc.pdf",
                "to": "John Doe",
                "email": "john@example.com",
            },
        )
        assert result.success is False
        assert result.error_code == "FILE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_email_not_configured(self, plugin, test_document):
        """Test email without SMTP configuration."""
        # Without SMTP config, email will fail
        result = await plugin.execute(
            "email",
            {
                "document": test_document,
                "to": "John Doe",
                "email": "john@example.com",
                "subject": "Test",
            },
        )
        # Email should fail without SMTP config
        assert result.success is False

    @pytest.mark.asyncio
    async def test_fax_not_configured(self, plugin, test_document):
        """Test fax without simple-fax config."""
        result = await plugin.execute(
            "fax",
            {
                "document": test_document,
                "to": "John Doe",
                "fax": "+49 221 12345678",
            },
        )
        assert result.success is False
        assert result.error_code == "NOT_CONFIGURED"

    @pytest.mark.asyncio
    async def test_post_not_configured(self, plugin, test_document):
        """Test post without LetterXpress config."""
        result = await plugin.execute(
            "post",
            {
                "document": test_document,
                "to": "John Doe",
                "street": "Main St 1",
                "plz": "50858",
                "city": "Cologne",
            },
        )
        assert result.success is False
        assert result.error_code == "NOT_CONFIGURED"

    @pytest.mark.asyncio
    async def test_bea_not_configured(self, plugin, test_document):
        """Test beA without config."""
        result = await plugin.execute(
            "bea",
            {
                "document": test_document,
                "to": "AG Köln",
                "safe_id": "DE.BRAK.12345",
                "reference": "123 C 456/24",
            },
        )
        assert result.success is False
        assert result.error_code == "NOT_CONFIGURED"

    @pytest.mark.asyncio
    async def test_channels(self, plugin):
        """Test listing channels."""
        result = await plugin.execute("channels", {})
        assert result.success is True
        assert "channels" in result.data
        assert len(result.data["channels"]) == 4

        # All should show as not configured
        for channel in result.data["channels"]:
            assert channel["configured"] is False

    @pytest.mark.asyncio
    async def test_history_empty(self, plugin):
        """Test history with no transmissions."""
        result = await plugin.execute("history", {})
        assert result.success is True
        assert result.data["count"] == 0
        assert result.data["transmissions"] == []

    @pytest.mark.asyncio
    async def test_history_with_filter(self, plugin, test_document):
        """Test history with filters."""
        # Create a failed transmission
        await plugin.execute(
            "fax",
            {
                "document": test_document,
                "to": "Test",
                "fax": "+49 123",
            },
        )

        # Filter by channel
        result = await plugin.execute(
            "history",
            {"channel": "fax"},
        )
        assert result.success is True
        assert result.data["count"] == 1

        # Filter by email (should be empty)
        result = await plugin.execute(
            "history",
            {"channel": "email"},
        )
        assert result.success is True
        assert result.data["count"] == 0

    @pytest.mark.asyncio
    async def test_history_invalid_channel(self, plugin):
        """Test history with invalid channel filter."""
        result = await plugin.execute(
            "history",
            {"channel": "invalid"},
        )
        assert result.success is False
        assert result.error_code == "INVALID_INPUT"

    @pytest.mark.asyncio
    async def test_get_not_found(self, plugin):
        """Test getting non-existent transmission."""
        result = await plugin.execute(
            "get",
            {"transmission_id": "nonexistent"},
        )
        assert result.success is False
        assert result.error_code == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_get_transmission(self, plugin, test_document):
        """Test getting a transmission."""
        # Create a transmission first
        await plugin.execute(
            "fax",
            {
                "document": test_document,
                "to": "Test Recipient",
                "fax": "+49 123 456",
                "reference": "REF-123",
            },
        )

        # Get from history
        history = await plugin.execute("history", {})
        tid = history.data["transmissions"][0]["transmission_id"]

        # Get by ID
        result = await plugin.execute("get", {"transmission_id": tid})
        assert result.success is True
        assert result.data["transmission_id"] == tid
        assert result.data["reference"] == "REF-123"

    @pytest.mark.asyncio
    async def test_stats(self, plugin, test_document):
        """Test getting stats."""
        # Create some transmissions
        for _ in range(3):
            await plugin.execute(
                "fax",
                {
                    "document": test_document,
                    "to": "Test",
                    "fax": "+49 123",
                },
            )

        result = await plugin.execute("stats", {})
        assert result.success is True
        assert result.data["total"] == 3


class TestChannelResult:
    """Tests for ChannelResult."""

    def test_success_result(self):
        """Test successful result."""
        result = ChannelResult(
            success=True,
            message="Email sent successfully",
            metadata={"message_id": "123"},
        )
        assert result.success is True
        assert result.message == "Email sent successfully"
        assert result.metadata["message_id"] == "123"

    def test_error_result(self):
        """Test error result."""
        result = ChannelResult(
            success=False,
            error="Connection refused",
        )
        assert result.success is False
        assert result.error == "Connection refused"
