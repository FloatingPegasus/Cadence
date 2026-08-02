from sqlalchemy import Column, Integer, ForeignKey, UniqueConstraint

from ...extensions import Base


class HabitLog(Base):
    __tablename__ = "habit_logs"

    id = Column(Integer, primary_key=True)
    habit_id = Column(Integer, ForeignKey("habits.id"), nullable=False)
    day_id = Column(Integer, ForeignKey("days.id"), nullable=False)

    __table_args__ = (
        UniqueConstraint("day_id", "habit_id", name="day_habit_uc"),
    )
