from academyagentapp.model import *
from academyagentapp import db, app

def create_all():
    with app.app_context():
        db.create_all()

def delete_all():
    with app.app_context():
        db.drop_all

def create_table(table):
  with app.app_context():
    table.__table__.create(db.engine)

def drop_table(table):
  with app.app_context():
    table.__table__.drop(db.engine)

def list_all_records(table):
    with app.app_context():
        records = table.query.all()

        for record in records:
            print(record)

        print(f"There are {len(records)} Records")