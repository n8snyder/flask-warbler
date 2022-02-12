"""Message model tests."""

# run these tests like:
#
#    python -m unittest test_message_model.py

import os
from datetime import datetime
from unittest import TestCase

from models import (
    db,
    User,
    Message,
    Follows,
)

# BEFORE we import our app, let's set an environmental variable
# to use a different database for tests (we need to do this
# before we import our app, since that will have already
# connected to the database

os.environ["DATABASE_URL"] = "postgresql:///warbler_test"

# Now we can import app

from app import app

# Create our tables (we do this here, so we only create the tables
# once for all tests --- in each test, we'll delete the data
# and create fresh new clean test data

db.create_all()


class UserModelTestCase(TestCase):
    """Test views for messages."""

    def setUp(self):
        """Create test client, add sample data."""

        User.query.delete()
        Follows.query.delete()

        self.client = app.test_client()
        self.username = "user"
        self.email = "foo1@bar.com"
        user = User(
            email=self.email,
            username=self.username,
            password="HASHED_PASSWORD",
        )
        db.session.add(user)
        db.session.commit()
        self.user_id = user.id

    def tearDown(self):
        """Clean up fouled transactions."""

        db.session.rollback()

    def test_message_model(self):
        """Does basic message model work?"""

        before = datetime.utcnow()

        message = Message(text="new message", user_id=self.user_id)
        db.session.add(message)
        db.session.commit()

        after = datetime.utcnow()

        self.assertEqual(message.text, "new message")
        self.assertEqual(message.user_id, self.user_id)
        self.assertGreater(message.timestamp, before)
        self.assertLess(message.timestamp, after)

    def test_is_liked_by(self):
        """Does is_liked_by correctly indicate if user has liked the message?"""

        # Create second user
        user2 = User(
            email="foo2@bar.com",
            username="user2",
            password="HASHED_PASSWORD",
        )
        db.session.add(user2)
        db.session.commit()

        # Create message
        message = Message(text="new message", user_id=self.user_id)
        db.session.add(message)
        db.session.commit()

        # The message shouldn't be liked by user2
        self.assertFalse(message.is_liked_by(user2))

        # user2 likes the message
        user2.liked_messages.append(message)
        db.session.commit()

        # The message should be liked by user2
        self.assertTrue(message.is_liked_by(user2))
