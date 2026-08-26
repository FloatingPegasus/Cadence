from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from ...extensions import Base


GOAL_KINDS = ("ultimate", "secondary", "short_term", "long_term")


class UserGoal(Base):
    __tablename__ = "user_goals"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    kind = Column(String(20), nullable=False)
    title = Column(String(200), nullable=False)
    notes = Column(Text, nullable=False, default="")
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
