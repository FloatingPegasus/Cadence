from sqlalchemy import (
    Boolean,
    Column,
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


class SummaryArtifact(Base):
    __tablename__ = "summary_artifacts"

    id = Column(Integer, primary_key=True)
    day_id = Column(Integer, ForeignKey("days.id"), nullable=False)
    kind = Column(String(30), nullable=False, default="daily")
    content = Column(Text, nullable=False, default="")
    provider = Column(String(40))
    model = Column(String(255))
    prompt_version = Column(String(40), nullable=False)
    source_fingerprint = Column(String(64), nullable=False)
    source_snapshot = Column(Text, nullable=False)
    is_user_edited = Column(Boolean, nullable=False, default=False)
    generated_at = Column(DateTime)
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("day_id", "kind", name="day_summary_kind_uc"),
        Index(
            "ix_summary_artifacts_content_trgm",
            "content",
            postgresql_using="gin",
            postgresql_ops={"content": "gin_trgm_ops"},
        ),
    )
