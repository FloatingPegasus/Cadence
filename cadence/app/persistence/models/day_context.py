from sqlalchemy import Column, ForeignKey, Index, Integer

from ...extensions import Base


class DayContext(Base):
    __tablename__ = "day_contexts"

    day_id = Column(Integer, ForeignKey("days.id"), primary_key=True)
    context_id = Column(Integer, ForeignKey("contexts.id"), primary_key=True)

    __table_args__ = (
        Index(
            "ix_day_contexts_context_day",
            "context_id",
            "day_id",
        ),
    )
