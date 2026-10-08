from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'owner' or 'manager'
    email = db.Column(db.String(150))
    phone_number = db.Column(db.String(20))
    is_verified = db.Column(db.Boolean, default=False)
    otp_code = db.Column(db.String(6))
    otp_expiry = db.Column(db.DateTime)


class Campaign(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    target_audience = db.Column(db.String(150))
    platform = db.Column(db.String(50))
    goal = db.Column(db.String(100))
    tone = db.Column(db.String(50))
    marketing_type = db.Column(db.String(50))
    language = db.Column(db.String(20), default='English')
    content_mode = db.Column(db.String(20), default='AI')  # 'AI' or 'Template'
    banner_headline = db.Column(db.String(200))
    banner_subtext = db.Column(db.String(200))
    status = db.Column(db.String(20), default='Draft')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    variations = db.relationship('ContentVariation', backref='campaign', lazy=True, cascade="all, delete-orphan")
    approval = db.relationship('Approval', backref='campaign', uselist=False, cascade="all, delete-orphan")


class ContentVariation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'), nullable=False)
    headline = db.Column(db.String(200))
    caption = db.Column(db.Text)
    cta = db.Column(db.String(100))
    sentiment_score = db.Column(db.Float)
    is_recommended = db.Column(db.Boolean, default=False)


class Approval(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'), nullable=False)
    manager_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    comment = db.Column(db.Text)
    decision = db.Column(db.String(20))  # Approved / Rejected
    reviewed_at = db.Column(db.DateTime, default=datetime.utcnow)



class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150))
    email = db.Column(db.String(150), nullable=False)
    preferred_language = db.Column(db.String(20), default='English')
    is_verified = db.Column(db.Boolean, default=False)
    otp_code = db.Column(db.String(6))
    otp_expiry = db.Column(db.DateTime)
