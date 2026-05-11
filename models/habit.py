from flask_sqlalchemy import SQLAlchemy
from .database import db

class Habit(db.Model):
    __tablename__ = 'habits'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable = False)
    name = db.Column(db.String(100), nullable = False)
    # target = db.Column(db.Integer, nullable = False)
    # created_at = db.Column(db.Integer, nullable = False)
    # is_active = db.Column(db.Boolean, nullable = False)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'name', name='user_habitname_uc'),
    )