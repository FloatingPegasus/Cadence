from sqlalchemy import Boolean, Column, ForeignKey, Index, Integer, String, text

from ...extensions import Base


class Habit(Base):
    __tablename__ = "habits"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    is_archived = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index(
            "uq_active_user_habit_name",
            "user_id",
            "name",
            unique=True,
            sqlite_where=text("is_archived = 0"),
        ),
        Index(
            "ix_habits_user_archived_id",
            "user_id",
            "is_archived",
            "id",
        ),
    )
