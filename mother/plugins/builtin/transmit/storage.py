"""Transmission history storage using SQLite."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class TransmissionChannel(str, Enum):
    """Available transmission channels."""

    EMAIL = "email"
    FAX = "fax"
    POST = "post"
    BEA = "bea"


class TransmissionStatus(str, Enum):
    """Transmission status."""

    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Recipient:
    """Recipient information."""

    name: str
    email: str | None = None
    fax: str | None = None
    street: str | None = None
    plz: str | None = None
    city: str | None = None
    country: str = "DE"
    safe_id: str | None = None  # For beA

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "email": self.email,
            "fax": self.fax,
            "street": self.street,
            "plz": self.plz,
            "city": self.city,
            "country": self.country,
            "safe_id": self.safe_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Recipient:
        """Create from dictionary."""
        return cls(
            name=data.get("name", ""),
            email=data.get("email"),
            fax=data.get("fax"),
            street=data.get("street"),
            plz=data.get("plz"),
            city=data.get("city"),
            country=data.get("country", "DE"),
            safe_id=data.get("safe_id"),
        )


@dataclass
class Transmission:
    """Represents a document transmission."""

    transmission_id: str
    channel: TransmissionChannel
    status: TransmissionStatus
    document_path: str
    recipient: Recipient
    subject: str = ""
    cover_text: str = ""
    reference: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    sent_at: datetime | None = None
    delivered_at: datetime | None = None
    error_message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "transmission_id": self.transmission_id,
            "channel": self.channel.value,
            "status": self.status.value,
            "document_path": self.document_path,
            "recipient": self.recipient.to_dict(),
            "subject": self.subject,
            "cover_text": self.cover_text,
            "reference": self.reference,
            "created_at": self.created_at.isoformat(),
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }

    def summary(self) -> dict[str, Any]:
        """Get brief summary."""
        return {
            "transmission_id": self.transmission_id,
            "channel": self.channel.value,
            "status": self.status.value,
            "recipient": self.recipient.name,
            "subject": self.subject,
            "reference": self.reference,
            "created_at": self.created_at.isoformat(),
        }


class TransmissionStore:
    """SQLite-based transmission history storage."""

    def __init__(self, db_path: Path | None = None):
        """Initialize transmission store.

        Args:
            db_path: Path to SQLite database. Defaults to ~/.config/mother/transmit.db
        """
        if db_path is None:
            db_path = Path.home() / ".config" / "mother" / "transmit.db"

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS transmissions (
                    transmission_id TEXT PRIMARY KEY,
                    channel TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    document_path TEXT NOT NULL,
                    recipient TEXT NOT NULL,
                    subject TEXT,
                    cover_text TEXT,
                    reference TEXT,
                    created_at TEXT NOT NULL,
                    sent_at TEXT,
                    delivered_at TEXT,
                    error_message TEXT,
                    metadata TEXT
                )
            """)

            # Create indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_transmissions_channel ON transmissions(channel)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_transmissions_status ON transmissions(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_transmissions_reference ON transmissions(reference)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_transmissions_created ON transmissions(created_at)")

            conn.commit()

    def generate_id(self) -> str:
        """Generate a unique transmission ID."""
        return str(uuid.uuid4())[:8]

    def add_transmission(self, transmission: Transmission) -> str:
        """Add a new transmission record.

        Args:
            transmission: Transmission to add

        Returns:
            Transmission ID
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO transmissions (
                    transmission_id, channel, status, document_path, recipient,
                    subject, cover_text, reference, created_at, sent_at,
                    delivered_at, error_message, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    transmission.transmission_id,
                    transmission.channel.value,
                    transmission.status.value,
                    transmission.document_path,
                    json.dumps(transmission.recipient.to_dict()),
                    transmission.subject,
                    transmission.cover_text,
                    transmission.reference,
                    transmission.created_at.isoformat(),
                    transmission.sent_at.isoformat() if transmission.sent_at else None,
                    transmission.delivered_at.isoformat() if transmission.delivered_at else None,
                    transmission.error_message,
                    json.dumps(transmission.metadata),
                ),
            )
            conn.commit()

        return transmission.transmission_id

    def get_transmission(self, transmission_id: str) -> Transmission | None:
        """Get a transmission by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM transmissions WHERE transmission_id = ?",
                (transmission_id,),
            ).fetchone()

            if not row:
                return None

            return self._row_to_transmission(row)

    def update_status(
        self,
        transmission_id: str,
        status: TransmissionStatus,
        error_message: str = "",
    ) -> bool:
        """Update transmission status."""
        now = datetime.now()

        with sqlite3.connect(self.db_path) as conn:
            updates = ["status = ?"]
            params: list[Any] = [status.value]

            if status == TransmissionStatus.SENT:
                updates.append("sent_at = ?")
                params.append(now.isoformat())
            elif status == TransmissionStatus.DELIVERED:
                updates.append("delivered_at = ?")
                params.append(now.isoformat())
            elif status == TransmissionStatus.FAILED:
                updates.append("error_message = ?")
                params.append(error_message)

            params.append(transmission_id)

            cursor = conn.execute(
                f"UPDATE transmissions SET {', '.join(updates)} WHERE transmission_id = ?",
                params,
            )
            conn.commit()
            return cursor.rowcount > 0

    def list_transmissions(
        self,
        channel: TransmissionChannel | None = None,
        status: TransmissionStatus | None = None,
        reference: str | None = None,
        limit: int = 50,
    ) -> list[Transmission]:
        """List transmissions with optional filters."""
        conditions = []
        params: list[Any] = []

        if channel:
            conditions.append("channel = ?")
            params.append(channel.value)

        if status:
            conditions.append("status = ?")
            params.append(status.value)

        if reference:
            conditions.append("reference LIKE ?")
            params.append(f"%{reference}%")

        query = "SELECT * FROM transmissions"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_transmission(row) for row in rows]

    def get_stats(self) -> dict[str, Any]:
        """Get transmission statistics."""
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM transmissions").fetchone()[0]

            channel_counts = conn.execute("SELECT channel, COUNT(*) FROM transmissions GROUP BY channel").fetchall()

            status_counts = conn.execute("SELECT status, COUNT(*) FROM transmissions GROUP BY status").fetchall()

            # Recent transmissions (last 7 days)
            recent = conn.execute(
                """
                SELECT COUNT(*) FROM transmissions
                WHERE created_at > datetime('now', '-7 days')
                """
            ).fetchone()[0]

            return {
                "total": total,
                "by_channel": {row[0]: row[1] for row in channel_counts},
                "by_status": {row[0]: row[1] for row in status_counts},
                "recent_7_days": recent,
            }

    def _row_to_transmission(self, row: sqlite3.Row) -> Transmission:
        """Convert database row to Transmission object."""
        recipient_data = json.loads(row["recipient"])

        return Transmission(
            transmission_id=row["transmission_id"],
            channel=TransmissionChannel(row["channel"]),
            status=TransmissionStatus(row["status"]),
            document_path=row["document_path"],
            recipient=Recipient.from_dict(recipient_data),
            subject=row["subject"] or "",
            cover_text=row["cover_text"] or "",
            reference=row["reference"] or "",
            created_at=datetime.fromisoformat(row["created_at"]),
            sent_at=datetime.fromisoformat(row["sent_at"]) if row["sent_at"] else None,
            delivered_at=datetime.fromisoformat(row["delivered_at"]) if row["delivered_at"] else None,
            error_message=row["error_message"] or "",
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )
