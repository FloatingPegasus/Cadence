from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, func

from ...extensions import Base


class CarryForwardItem(Base):
    __tablename__ = "carry_forward_items"
    __table_args__ = (
        Index("ix_carry_forward_origin_status", "origin_day_id", "status"),
        Index("ix_carry_forward_status_origin", "status", "origin_day_id"),
    )

    id = Column(Integer, primary_key=True)
    origin_day_id = Column(Integer, ForeignKey("days.id"), nullable=False)
    content = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="open")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    resolved_at = Column(DateTime)
