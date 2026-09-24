from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)

from ...extensions import Base


class ConversationEntry(Base):
    __tablename__ = "conversation_entries"
    __table_args__ = (
        Index(
            "ix_conversation_entries_day_created",
            "day_id",
            "created_at",
        ),
        Index(
            "ix_conversation_entries_content_trgm",
            "content",
            postgresql_using="gin",
            postgresql_ops={"content": "gin_trgm_ops"},
        ),
        CheckConstraint(
            "hour IS NULL OR (hour >= 0 AND hour <= 23)",
            name="conversation_entry_hour_range",
        ),
    )

    id = Column(Integer, primary_key=True)
    day_id = Column(Integer, ForeignKey("days.id"), nullable=False)
    role = Column(String(30), default="user")
    content = Column(Text, nullable=False)
    hour = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())
