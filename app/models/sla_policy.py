from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SLAPolicy(Base):
    __tablename__ = "sla_policies"

    priority: Mapped[str] = mapped_column(String(20), primary_key=True)  # baja|media|alta|critica
    response_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    resolution_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
