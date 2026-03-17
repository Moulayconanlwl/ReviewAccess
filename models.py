from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id            = db.Column(db.Integer, primary_key=True)
    email         = db.Column(db.String(200), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role          = db.Column(db.String(20), default="filter_owner")  # 'admin' or 'filter_owner'
    owner_key     = db.Column(db.String(200), nullable=True)          # matches 'Data entry filter owner'
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

class ReviewSession(db.Model):
    __tablename__ = "review_sessions"
    id          = db.Column(db.String(32), primary_key=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    deadline    = db.Column(db.String(20))
    quarter     = db.Column(db.String(20))
    created_by  = db.Column(db.String(200))
    rows        = db.relationship("UserRow", backref="session", lazy=True, cascade="all, delete-orphan")

class UserRow(db.Model):
    __tablename__ = "user_rows"
    id                 = db.Column(db.Integer, primary_key=True)
    session_id         = db.Column(db.String(32), db.ForeignKey("review_sessions.id"))
    code               = db.Column(db.String(50))
    user_name          = db.Column(db.String(200))
    functional_profile = db.Column(db.String(100))
    data_entry_access  = db.Column(db.String(200))
    manager            = db.Column(db.String(200))
    departement        = db.Column(db.String(200))
    location           = db.Column(db.String(100))
    filter_owner       = db.Column(db.String(200), index=True)
    active_bfc         = db.Column(db.String(10))
    active_ad          = db.Column(db.String(10))
    extra_data         = db.Column(db.JSON)
    choice             = db.Column(db.String(20), default="pending")
    validator          = db.Column(db.String(200))
    validated_at       = db.Column(db.DateTime, nullable=True)
    signoff_at         = db.Column(db.DateTime, nullable=True)

class Delegation(db.Model):
    __tablename__ = "delegations"
    id           = db.Column(db.Integer, primary_key=True)
    session_id   = db.Column(db.String(32), db.ForeignKey("review_sessions.id"))
    owner_key    = db.Column(db.String(200))
    delegate_key = db.Column(db.String(200))
