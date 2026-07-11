from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # 'usuario' | 'tecnico' | 'supervisor' | 'admin'
    area_id: Mapped[int | None] = mapped_column(ForeignKey("areas.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    area = relationship("Area", back_populates="users")
    reported_tickets = relationship(
        "Ticket", foreign_keys="Ticket.reporter_id", back_populates="reporter"
    )
    assigned_tickets = relationship(
        "Ticket", foreign_keys="Ticket.assigned_to_id", back_populates="assigned_to"
    )
