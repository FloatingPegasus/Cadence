from flask_sqlalchemy import SQLAlchemy
from .database import db
# from datetime import date

class HabitLog(db.Model):
    __tablename__ = 'habit_logs'

    id = db.Column(db.Integer, primary_key=True)
    habit_id = db.Column(db.Integer, db.ForeignKey('habits.id'), nullable = False)
    user_id = db.Column(db.Integer, nullable = False)
    date = db.Column(db.Date, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'habit_id', 'date', name='user_habit_date_uc'),
    )