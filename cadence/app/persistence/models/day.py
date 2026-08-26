from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)

from ...extensions import Base


class Day(Base):
    __tablename__ = "days"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(Date, nullable=False)
    status = Column(String(20), default="open")
    daily_note = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="user_day_uc"),
        Index(
            "ix_days_daily_note_trgm",
            "daily_note",
            postgresql_using="gin",
            postgresql_ops={"daily_note": "gin_trgm_ops"},
        ),
    )
