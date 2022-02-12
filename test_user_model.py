"""User model tests."""

# run these tests like:
#
#    python -m unittest test_user_model.py

import os
from unittest import TestCase

from models import (
    db,
    User,
    Follows,
    DEFAULT_IMAGE,
    DEFAULT_HEADER,
    bcrypt,
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
        self.password = "FeL7f23#1"
        self.username1 = "user1"
        self.email1 = "foo1@bar.com"
        self.username2 = "user2"
        self.email2 = "foo2@bar.com"
        user1 = User(
            email=self.email1,
            username=self.username1,
            password=bcrypt.generate_password_hash(self.password).decode(
                "UTF-8"
            ),
        )
        user2 = User(
            email=self.email2,
            username=self.username2,
            password=bcrypt.generate_password_hash(self.password).decode(
                "UTF-8"
            ),
        )
        db.session.add_all([user1, user2])
        db.session.commit()
        self.user1_id = user1.id
        self.user2_id = user2.id

    def tearDown(self):
        """Clean up fouled transactions."""

        db.session.rollback()

    def test_user_model(self):
        """Does basic model work?"""

        user = User(
            email="test@test.com",
            username="testuser",
            password="HASHED_PASSWORD",
        )

        db.session.add(user)
        db.session.commit()

        # User should have no messages & no followers
        self.assertEqual(len(user.messages), 0)
        self.assertEqual(len(user.followers), 0)

        # User should have default images
        self.assertEqual(user.image_url, DEFAULT_IMAGE)
        self.assertEqual(user.header_image_url, DEFAULT_HEADER)

        self.assertIs(user.bio, None)
        self.assertIs(user.location, None)

    def test_dunder_repr(self):
        """Are users correctly represented?"""

        user1 = User.query.get(self.user1_id)

        self.assertIn(str(self.user1_id), user1.__repr__())
        self.assertIn(self.username1, user1.__repr__())
        self.assertIn(self.email1, user1.__repr__())

    def test_is_following(self):
        """Does is_following correctly return if user is following?"""

        user1 = User.query.get(self.user1_id)
        user2 = User.query.get(self.user2_id)

        # User1 shouldn't be following user2
        self.assertFalse(user1.is_following(user2))

        # User1 follows user2
        user1.following.append(user2)
        db.session.commit()

        # User1 should be following user2
        self.assertTrue(user1.is_following(user2))

    def test_is_followed_by(self):
        """Does is_followed_by correctly return if user is followed by?"""

        user1 = User.query.get(self.user1_id)
        user2 = User.query.get(self.user2_id)

        # User1 shouldn't be followed by user2
        self.assertFalse(user1.is_followed_by(user2))

        # User1 becomes followed by user2
        user1.followers.append(user2)
        db.session.commit()

        # User1 should be followed by user2
        self.assertTrue(user1.is_followed_by(user2))

    def test_signup(self):
        """Does User.signup create a new user?"""

        user = User.signup(
            "unique_username",
            "unique@mail.com",
            "123123",
            "static/images/default-pic.png",
        )

        # Are the attributes correct?
        self.assertEqual(user.username, "unique_username")
        self.assertEqual(user.email, "unique@mail.com")
        self.assertEqual(user.image_url, "static/images/default-pic.png")

        # Is the user in the database before commit?
        self.assertIsNone(user.id)

        db.session.commit()

        # Is the user in the database after commit?
        self.assertIsNotNone(user.id)

    def test_signup_fails_uniqueness(self):
        """Does User.signup fail when given non-unique values for unique fields?"""

        # Does signing up a user with a non-unique username fail?
        User.signup(
            self.username1,
            "unique@mail.com",
            "123123",
            "static/images/default-pic.png",
        )
        try:
            db.session.commit()
        except:
            # Correct behavior
            db.session.rollback()
        else:
            self.fail("Exception not raised.")

        # Does signing up a user with a non-unique email fail?
        User.signup(
            "unique_username",
            self.email1,
            "123123",
            "static/images/default-pic.png",
        )
        try:
            db.session.commit()
        except:
            # Correct behavior
            db.session.rollback()
        else:
            self.fail("Exception not raised.")

    def test_signup_fails_nullable(self):
        """Does User.signup fail when given None for non-nullable fields?"""

        # Does signing up a user with username of None fail?
        User.signup(
            None,
            "user3@foo.bar",
            "123123",
            "static/images/default-pic.png",
        )
        try:
            db.session.commit()
        except:
            # Correct behavior
            db.session.rollback()
        else:
            self.fail("Exception not raised when username is null.")

        # Does signing up a user with email of None fail?
        User.signup(
            "unique_username",
            None,
            "123123",
            "static/images/default-pic.png",
        )
        try:
            db.session.commit()
        except:
            # Correct behavior
            db.session.rollback()
        else:
            self.fail("Exception not raised when email is null.")

        # Does signing up a user with password of None fail?
        try:
            User.signup(
                "unique_username",
                "user3@foo.bar",
                None,
                "static/images/default-pic.png",
            )
        except:
            # Correct behavior
            pass
        else:
            self.fail("Exception not raised when password is null.")

    def test_authenticate(self):
        """Does User.authenticate return user when valid username, password?"""

        user = User.authenticate(self.username1, self.password)

        self.assertEqual(user.id, self.user1_id)

    def test_authenticate_fails(self):
        """Does User.authenticate return False when username, password invalid?"""

        # Does authenticating with invalid username return False?
        result = User.authenticate("invalid_username", self.password)

        self.assertFalse(result)

        # Does authenticating with invalid password return False?
        result = User.authenticate(self.username1, "invalid password")

        self.assertFalse(result)
