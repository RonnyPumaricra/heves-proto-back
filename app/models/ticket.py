from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="media", nullable=False)  # baja|media|alta|critica
    status: Mapped[str] = mapped_column(String(20), default="CREADO", nullable=False)  # CREADO|ASIGNADO|EN_PROCESO|RESUELTO|CERRADO
    area_id: Mapped[int | None] = mapped_column(ForeignKey("areas.id"), nullable=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    assigned_to_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sla_response_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sla_resolution_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id"), nullable=True)

    area = relationship("Area", back_populates="tickets")
    device = relationship("Device")
    reporter = relationship("User", foreign_keys=[reporter_id], back_populates="reported_tickets")
    assigned_to = relationship("User", foreign_keys=[assigned_to_id], back_populates="assigned_tickets")
    comments = relationship("Comment", back_populates="ticket", cascade="all, delete-orphan")
    attachments = relationship("Attachment", back_populates="ticket", cascade="all, delete-orphan")
