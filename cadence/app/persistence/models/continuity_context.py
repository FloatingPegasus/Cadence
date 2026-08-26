from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)

from ...extensions import Base


class ContinuityContext(Base):
    __tablename__ = "contexts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    kind = Column(String(20), nullable=False, default="area")
    is_archived = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index(
            "uq_active_user_context_name",
            "user_id",
            "name",
            unique=True,
            postgresql_where=text("is_archived = false"),
        ),
        Index(
            "ix_contexts_user_archived_id",
            "user_id",
            "is_archived",
            "id",
        ),
    )
