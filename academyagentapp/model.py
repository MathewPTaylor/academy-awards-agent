from academyagentapp import db
from flask_sqlalchemy import SQLAlchemy

db: SQLAlchemy

class Users(db.Model):
    id = db.Column(db.Integer, primary_key=True, nullable=False)
    username = db.Column(db.String(), nullable=False, unique=True)
    password = db.Column(db.String(), nullable=False)
    conversations = db.relationship('Conversations', backref='user', lazy='dynamic')

    @classmethod
    def get_username(cls, user_id):
        query = db.select(cls).where(cls.id == user_id)
        user = db.session.execute(query).first()

        return user[0].username if user else None

    def __repr__(self):
        return f"User({self.username})"


class Conversations(db.Model):
    id = db.Column(db.Integer, primary_key=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    conversation_id = db.Column(db.String(), nullable=False)
    summary_title = db.Column(db.String(), nullable=False)

    def __repr__(self):
        return f"Conversation({self.user_id}, {self.conversation_id}, {self.summary_title})"

