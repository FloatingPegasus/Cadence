from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)

from ...extensions import Base


class HourLog(Base):
    __tablename__ = "hour_logs"
    __table_args__ = (
        UniqueConstraint("day_id", "hour", name="day_hour_uc"),
        CheckConstraint("hour >= 0 AND hour <= 23", name="hour_range"),
        Index("ix_hour_logs_day_id", "day_id"),
    )

    id = Column(Integer, primary_key=True)
    day_id = Column(Integer, ForeignKey("days.id"), nullable=False)
    hour = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
