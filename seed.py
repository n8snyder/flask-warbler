"""Seed database with sample data from CSV Files."""

from sqlalchemy.sql.expression import func

from csv import DictReader
from app import db
from models import User, Message, Follows

db.drop_all()
db.create_all()

with open("generator/users.csv") as users:
    db.session.bulk_insert_mappings(User, DictReader(users))

with open("generator/messages.csv") as messages:
    db.session.bulk_insert_mappings(Message, DictReader(messages))

with open("generator/follows.csv") as follows:
    db.session.bulk_insert_mappings(Follows, DictReader(follows))

db.session.commit()


user = User(
    username="test",
    email="test@fd.ew",
    password="$2b$12$z6FbBI3B5hIlMG7Y2/k.5erXCUXWg4FEhis/D7LmaDINlPSgItudq",
)

db.session.add(user)
db.session.commit()

followers = User.query.order_by(func.random()).limit(10).all()
following = User.query.order_by(func.random()).limit(10).all()
user.followers += followers
user.following += following
db.session.commit()
