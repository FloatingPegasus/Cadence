from sqlalchemy import Boolean, CheckConstraint, Column, Integer, SmallInteger, String, text

from ...extensions import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "day_ends_at >= 0 AND day_ends_at <= 12",
            name="user_day_ends_at_range",
        ),
    )

    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True, index=True)
    hashed_password = Column(String(128), nullable=False)
    is_verified = Column(Boolean, nullable=False, default=False)
    is_guest = Column(Boolean, nullable=False, default=False)
    ai_processing_consent = Column(Boolean, nullable=False, default=False)
    ai_redaction_enabled = Column(Boolean, nullable=False, default=True)
    day_ends_at = Column(
        SmallInteger, nullable=False, default=4, server_default=text("4")
    )
    auto_close = Column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
