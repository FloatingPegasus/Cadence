from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)

from ...extensions import Base


class WeeklyReflection(Base):
    __tablename__ = "weekly_reflections"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    week_start = Column(Date, nullable=False)
    content = Column(Text, nullable=False, default="")
    provider = Column(String(40))
    model = Column(String(255))
    prompt_version = Column(String(40), nullable=False)
    source_fingerprint = Column(String(64), nullable=False)
    source_snapshot = Column(Text, nullable=False)
    is_user_edited = Column(Boolean, nullable=False, default=False)
    generated_at = Column(DateTime)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "week_start",
            name="user_weekly_reflection_uc",
        ),
    )
