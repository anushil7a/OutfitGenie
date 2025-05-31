from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    height = db.Column(db.Float)
    weight = db.Column(db.Float)
    gender = db.Column(db.String(20))
    preferences = db.Column(db.JSON)
    ai_notes = db.Column(db.Text)  # Add AI notes field
    outfits = db.relationship('Outfit', backref='user', lazy=True)
    chats = db.relationship('Chat', backref='user', lazy=True)
    feedback = db.relationship('RecommendationFeedback', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Outfit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    image_url = db.Column(db.String(255))
    analysis = db.Column(db.Text)
    items = db.Column(db.JSON)
    occasion = db.Column(db.String(50))
    weather = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    rating = db.Column(db.Integer)

class Chat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    messages = db.Column(db.JSON)  # List of messages with sender and text
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'preview': self.messages[0]['text'][:50] + '...' if self.messages else 'New Chat',
            'timestamp': self.created_at.isoformat()
        }

class RecommendationFeedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recommendation = db.Column(db.Text, nullable=False)  # The recommendation text
    question = db.Column(db.Text, nullable=False)  # The user's question that led to the recommendation
    feedback = db.Column(db.String(10), nullable=False)  # 'like' or 'dislike'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    context = db.Column(db.JSON)  # Store context like occasion, weather, etc.

    def to_dict(self):
        return {
            'id': self.id,
            'recommendation': self.recommendation,
            'question': self.question,
            'feedback': self.feedback,
            'created_at': self.created_at.isoformat(),
            'context': self.context
        }

class ClothingItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    outfit_id = db.Column(db.Integer, db.ForeignKey('outfit.id'), nullable=False)
    type = db.Column(db.String(50))
    color = db.Column(db.String(50))
    brand = db.Column(db.String(100))
    material = db.Column(db.String(100))
    key_features = db.Column(db.Text)
    overall_vibe = db.Column(db.String(50))
    short_description = db.Column(db.Text)  # For the paragraph format
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'color': self.color,
            'brand': self.brand,
            'material': self.material,
            'key_features': self.key_features,
            'overall_vibe': self.overall_vibe,
            'short_description': self.short_description
        } 