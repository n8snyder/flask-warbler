"""Message View tests."""

# run these tests like:
#
#    FLASK_ENV=production python -m unittest test_message_views.py


import os
from unittest import TestCase

from models import db, connect_db, Message, User

# BEFORE we import our app, let's set an environmental variable
# to use a different database for tests (we need to do this
# before we import our app, since that will have already
# connected to the database

os.environ["DATABASE_URL"] = "postgresql:///warbler_test"

# Now we can import app

from app import app, CURR_USER_KEY

# Create our tables (we do this here, so we only create the tables
# once for all tests --- in each test, we'll delete the data
# and create fresh new clean test data

db.create_all()

# Don't have WTForms use CSRF at all, since it's a pain to test

app.config["WTF_CSRF_ENABLED"] = False


class MessageViewTestCase(TestCase):
    """Test views for messages."""

    def setUp(self):
        """Create test client, add sample data."""

        User.query.delete()
        Message.query.delete()

        self.client = app.test_client()

        self.username = "user"
        self.email = "test@test.com"
        user = User.signup(
            username=self.username,
            email=self.email,
            password="user",
            image_url=None,
        )
        db.session.commit()
        self.user_id = user.id

        self.text = "Hello World!"
        message = Message(text=self.text, user_id=self.user_id)
        db.session.add(message)
        db.session.commit()
        self.message_id = message.id

    def tearDown(self):
        """Clean up fouled transactions."""

        db.session.rollback()

    def test_get_add_message(self):
        """Can we access the add message page?"""

        with self.client as c:
            with c.session_transaction() as sess:
                sess[CURR_USER_KEY] = self.user_id

            resp = c.get("/messages/new")
            html = resp.get_data(as_text=True)

            # Should render the add message page
            self.assertEqual(resp.status_code, 200)
            self.assertIn("New Message Page", html)

    def test_get_add_message_logged_out(self):
        """Can we access the add message page when logged out?"""

        with self.client as c:
            resp = c.get("/messages/new")

            # Should redirect
            self.assertEqual(resp.status_code, 302)

    def test_post_add_message(self):
        """Can post a message?"""

        with self.client as c:
            with c.session_transaction() as sess:
                sess[CURR_USER_KEY] = self.user_id

            resp = c.post("/messages/new", data={"text": "New Message!"})

            # Make sure it redirects
            self.assertEqual(resp.status_code, 302)

            # Should have created the message
            message = Message.query.filter(
                Message.text == "New Message!"
            ).one()
            self.assertEqual(message.text, "New Message!")

    def test_add_message_logged_out(self):
        """Can we add a message when logged out?"""

        with self.client as c:
            resp = c.post(
                "/messages/new", data={"text": "UNIQUE_MESSAGE_TEXT"}
            )

            # Make sure it redirects
            self.assertEqual(resp.status_code, 302)

            # Shouldn't have created the message
            message = Message.query.filter(
                Message.text == "UNIQUE_MESSAGE_TEXT"
            ).one_or_none()
            self.assertIsNone(message)

    def test_add_message_empty(self):
        """Can we add an empty message?"""

        with self.client as c:
            with c.session_transaction() as sess:
                sess[CURR_USER_KEY] = self.user_id

            resp = c.post("/messages/new", data={"text": ""})
            html = resp.get_data(as_text=True)

            # Should rerender the form page with form error message
            self.assertEqual(resp.status_code, 200)
            self.assertIn("This field is required", html)

            # Shouldn't have created the message
            message = Message.query.filter(Message.text == "").one_or_none()
            self.assertIsNone(message)

    def test_show_message(self):
        """Can we view a message?"""

        with self.client as c:
            with c.session_transaction() as sess:
                sess[CURR_USER_KEY] = self.user_id

            resp = c.get(f"/messages/{self.message_id}")
            html = resp.get_data(as_text=True)

            # Should render the show message page
            self.assertEqual(resp.status_code, 200)
            self.assertIn("Show Message Page", html)

            # Should show the message somewhere on the page
            self.assertIn(self.text, html)

    def test_show_message_logged_out(self):
        """Can we view a message when logged out? (we should)"""

        with self.client as c:
            resp = c.get(f"/messages/{self.message_id}")
            html = resp.get_data(as_text=True)

            # Should render the show message page
            self.assertEqual(resp.status_code, 200)
            self.assertIn("Show Message Page", html)

            # Should show the message somewhere on the page
            self.assertIn(self.text, html)

    def test_show_message_invalid(self):
        """Do we get 404 for invalid message id?"""

        with self.client as c:
            resp = c.get("/messages/42000")

            # Should have statis code 404
            self.assertEqual(resp.status_code, 404)

    def test_messages_destroy(self):
        """Can we delete a message?"""

        with self.client as c:
            with c.session_transaction() as sess:
                sess[CURR_USER_KEY] = self.user_id

            resp = c.post(f"/messages/{self.message_id}/delete")

            # Should redirect
            self.assertEqual(resp.status_code, 302)

            # Should not be in database
            message = Message.query.filter(
                Message.id == self.message_id
            ).one_or_none()
            self.assertIsNone(message)

    def test_messages_destroy_logged_out(self):
        """Can we delete a message when logged out?"""

        with self.client as c:
            resp = c.post(f"/messages/{self.message_id}/delete")

            # Should redirect
            self.assertEqual(resp.status_code, 302)

            # Should still be in database
            message = Message.query.filter(
                Message.id == self.message_id
            ).one_or_none()
            self.assertIsNotNone(message)

    def test_messages_destroy_not_yours(self):
        """Can we delete a message from another user?"""

        # Create another user first
        user2 = User.signup(
            username="user2",
            email="user2@mail.com",
            password="user",
            image_url=None,
        )
        db.session.add(user2)
        db.session.commit()
        user2_id = user2.id

        with self.client as c:
            # Be logged in as user2
            with c.session_transaction() as sess:
                sess[CURR_USER_KEY] = user2_id

            # Try to delete another user message
            resp = c.post(f"/messages/{self.message_id}/delete")

            # Should be unauthorized
            self.assertEqual(resp.status_code, 401)

            # Should still be in database
            message = Message.query.filter(
                Message.id == self.message_id
            ).one_or_none()
            self.assertIsNotNone(message)

    def test_messages_destroy_invalid_id(self):
        """Do we 404 when trying to delete with invalid message_id?"""

        with self.client as c:
            with c.session_transaction() as sess:
                sess[CURR_USER_KEY] = self.user_id

            resp = c.post("/messages/420000/delete")

            # Should have 404 response code
            self.assertEqual(resp.status_code, 404)
