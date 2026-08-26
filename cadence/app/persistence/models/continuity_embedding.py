from sqlalchemy import (
    Boolean,
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
    text,
)
from pgvector.sqlalchemy import Vector

from ...extensions import Base


EMBEDDING_DIMENSIONS = 1024
CONTINUITY_EMBEDDING_DIMENSION = EMBEDDING_DIMENSIONS


class ContinuityEmbedding(Base):
    __tablename__ = "continuity_embeddings"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    source_type = Column(String(40), nullable=False)
    source_id = Column(Integer, nullable=False)
    day_id = Column(Integer, ForeignKey("days.id"), nullable=True)
    source_date = Column(Date, nullable=True)
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False)
    embedding_model = Column(String(255), nullable=False)
    embedding = Column(
        Vector(CONTINUITY_EMBEDDING_DIMENSION),
        nullable=False,
    )
    is_current = Column(Boolean, nullable=False, default=True)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "source_type",
            "source_id",
            name="user_embedding_source_uc",
        ),
        Index(
            "ix_continuity_embeddings_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_where=text("is_current IS TRUE"),
        ),
    )
