from academyagentapp import db
from flask_sqlalchemy import SQLAlchemy

db: SQLAlchemy


class ChatStates(db.Model):
    # id = db.Column(db.Integer, nullable=False)
    session_id = db.Column(db.String(20), primary_key=True, nullable=False)
    messages = db.Column(db.String(), nullable=True)
    next = db.Column(db.String(), nullable=True)

    def __repr__(self):
        return f"State(SID={self.session_id})"


class Variables(db.Model):
    name = db.Column(db.String(), primary_key=True)
    value = db.Column(db.String(), nullable=True)

    @classmethod
    def get_counter(cls):
        query = db.select(cls).where(cls.name == "counter")
        counter = db.session.execute(query).first()

        return counter[0]

    def __repr__(self):
        return f"Variable({self.name} = {self.value})"


class Users(db.Model):
    id = db.Column(db.Integer, primary_key=True, nullable=False)
    username = db.Column(db.String(), nullable=False, unique=True)
    password = db.Column(db.String(), nullable=False)

    @classmethod
    def get_username(cls, user_id):
        query = db.select(cls).where(cls.id == user_id)
        user = db.session.execute(query).first()

        return user[0].username if user else None

