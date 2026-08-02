from sqlalchemy import Boolean, Column, Integer, String

from ...extensions import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(128), nullable=False)
    is_verified = Column(Boolean, nullable=False, default=False)
    ai_processing_consent = Column(Boolean, nullable=False, default=False)
    ai_redaction_enabled = Column(Boolean, nullable=False, default=True)
