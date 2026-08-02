from sqlalchemy import Column, Integer, Float, String, Text, DateTime, ForeignKey, func

from ...extensions import Base


class DailyCheckin(Base):
    __tablename__ = "daily_checkins"

    id = Column(Integer, primary_key=True)
    day_id = Column(Integer, ForeignKey("days.id"), nullable=False, unique=True)
    sleep_hours = Column(Float)
    sleep_quality = Column(Integer)
    energy_level = Column(Integer)
    focus_quality = Column(Integer)
    emotional_state = Column(String(100))
    recovery_quality = Column(Integer)
    reentry_success = Column(Integer)
    drift_minutes = Column(Integer)
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())