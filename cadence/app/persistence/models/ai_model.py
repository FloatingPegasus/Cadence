from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)

from ...extensions import Base


class AIModel(Base):
    __tablename__ = "ai_models"

    id = Column(Integer, primary_key=True)
    provider = Column(String(40), nullable=False)
    model_id = Column(String(255), nullable=False)
    strength_score = Column(Integer, nullable=False, default=0)
    ranking_version = Column(String(40), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    health_status = Column(String(30), nullable=False, default="untested")
    latency_ms = Column(Float)
    last_error = Column(Text)
    first_seen_at = Column(DateTime, server_default=func.now(), nullable=False)
    last_seen_at = Column(DateTime, server_default=func.now(), nullable=False)
    last_tested_at = Column(DateTime)

    __table_args__ = (
        UniqueConstraint("provider", "model_id", name="provider_model_uc"),
    )
