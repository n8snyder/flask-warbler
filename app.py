import os

from flask import Flask, render_template, request, flash, redirect, session, g
from flask_debugtoolbar import DebugToolbarExtension
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
import dotenv
from werkzeug.exceptions import Unauthorized

from forms import (
    UserAddForm,
    LoginForm,
    MessageForm,
    UserEditForm,
    CSRFProtectForm,
)
from models import (
    db,
    connect_db,
    User,
    Message,
    Like,
    DEFAULT_HEADER,
    DEFAULT_IMAGE,
)

dotenv.load_dotenv()

CURR_USER_KEY = "curr_user"

app = Flask(__name__)

# Get DB_URI from environ variable (useful for production/testing) or,
# if not set there, use development local db.
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URL"].replace(
    "postgres://", "postgresql://"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ECHO"] = False
app.config["DEBUG_TB_INTERCEPT_REDIRECTS"] = False
app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
toolbar = DebugToolbarExtension(app)

connect_db(app)


##############################################################################
# User signup/login/logout


@app.before_request
def add_user_to_g():
    """If we're logged in, add curr user to Flask global."""

    if CURR_USER_KEY in session:
        g.user = User.query.get(session[CURR_USER_KEY])

    else:
        g.user = None


@app.before_request
def add_form_to_g():
    """Include CSRFProtectForm in Flask global.

    The form will have a hidden field of callback which is the path for this
    request. This allows for the form submition route to potentially redirect
    to where the form was submitted from.
    """

    g.csrf_form = CSRFProtectForm(callback=request.path)


def do_login(user):
    """Log in user."""

    session[CURR_USER_KEY] = user.id


def do_logout():
    """Logout user."""

    if CURR_USER_KEY in session:
        del session[CURR_USER_KEY]


@app.route("/signup", methods=["GET", "POST"])
def signup():
    """Handle user signup.

    Create new user and add to DB. Redirect to home page.

    If form not valid, present form.

    If the there already is a user with that username: flash message
    and re-present form.
    """

    form = UserAddForm()

    if form.validate_on_submit():
        try:
            user = User.signup(
                username=form.username.data,
                password=form.password.data,
                email=form.email.data,
                image_url=form.image_url.data
                if form.image_url.data
                else None,
            )
            db.session.commit()

        except IntegrityError:
            flash("Username already taken", "danger")
            return render_template("users/signup.html", form=form)

        do_login(user)

        return redirect("/")

    else:
        return render_template("users/signup.html", form=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Handle user login."""

    form = LoginForm()

    if form.validate_on_submit():
        user = User.authenticate(form.username.data, form.password.data)

        if user:
            do_login(user)
            flash(f"Hello, {user.username}!", "success")
            return redirect("/")

        flash("Invalid credentials.", "danger")

    return render_template("users/login.html", form=form)


@app.post("/logout")
def logout():
    """Handle logout of user."""

    form = CSRFProtectForm()
    if not form.validate_on_submit():
        raise Unauthorized()

    do_logout()
    flash("Successfully logged out!")
    return redirect("/")


##############################################################################
# General user routes:


@app.get("/users")
def list_users():
    """Page with listing of users.

    Can take a 'q' param in querystring to search by that username.
    """

    search = request.args.get("q")

    if not search:
        users = User.query.all()
    else:
        users = User.query.filter(User.username.like(f"%{search}%")).all()

    return render_template("users/index.html", users=users)


@app.get("/users/<int:user_id>")
def show_user(user_id):
    """Show user profile."""

    user = User.query.get_or_404(user_id)
    return render_template("users/show.html", user=user)


@app.get("/users/<int:user_id>/following")
def show_following(user_id):
    """Show list of people this user is following."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    user = User.query.get_or_404(user_id)
    return render_template("users/following.html", user=user)


@app.get("/users/<int:user_id>/followers")
def show_followers(user_id):
    """Show list of followers of this user."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    user = User.query.get_or_404(user_id)
    return render_template("users/followers.html", user=user)


@app.get("/users/<int:user_id>/likes")
def show_likes(user_id):
    """Show list of messages that are liked by this user."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    user = User.query.get_or_404(user_id)
    return render_template("users/likes.html", user=user)


@app.post("/users/follow/<int:follow_id>")
def add_follow(follow_id):
    """Add a follow for the currently-logged-in user."""

    form = CSRFProtectForm()
    if not form.validate_on_submit():
        raise Unauthorized()

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    followed_user = User.query.get_or_404(follow_id)
    g.user.following.append(followed_user)
    db.session.commit()

    return redirect(f"/users/{g.user.id}/following")


@app.post("/users/stop-following/<int:follow_id>")
def stop_following(follow_id):
    """Have currently-logged-in-user stop following this user."""

    form = CSRFProtectForm()
    if not form.validate_on_submit():
        raise Unauthorized()

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    followed_user = User.query.get(follow_id)
    g.user.following.remove(followed_user)
    db.session.commit()

    return redirect(f"/users/{g.user.id}/following")


@app.route("/users/profile", methods=["GET", "POST"])
def profile():
    """Update profile for current user."""

    if not g.user:
        raise Unauthorized("Not logged in.")

    user = User.query.get(session[CURR_USER_KEY])
    form = UserEditForm(obj=user)
    if form.validate_on_submit():
        if not User.authenticate(user.username, form.password.data):
            flash("Incorrect password.")
            return redirect("/")

        user.username = form.username.data
        user.email = form.email.data
        user.image_url = (
            form.image_url.data if form.image_url.data else DEFAULT_IMAGE
        )
        user.header_image_url = (
            form.header_image_url.data
            if form.header_image_url.data
            else DEFAULT_HEADER
        )
        user.bio = form.bio.data
        db.session.commit()
        return redirect(f"/users/{user.id}")
    else:
        form.image_url.data = (
            ""
            if form.image_url.data == DEFAULT_IMAGE
            else form.image_url.data
        )
        form.header_image_url.data = (
            ""
            if form.header_image_url.data == DEFAULT_HEADER
            else form.header_image_url.data
        )
        return render_template("users/edit.html", form=form)


@app.post("/users/delete")
def delete_user():
    """Delete user."""

    form = CSRFProtectForm()
    if not form.validate_on_submit():
        raise Unauthorized()

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    do_logout()

    db.session.delete(g.user)
    db.session.commit()

    return redirect("/signup")


##############################################################################
# Messages routes:


@app.route("/messages/new", methods=["GET", "POST"])
def messages_add():
    """Add a message:

    Show form if GET. If valid, update message and redirect to user page.
    """

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    form = MessageForm()

    if form.validate_on_submit():
        msg = Message(text=form.text.data)
        g.user.messages.append(msg)
        db.session.commit()

        return redirect(f"/users/{g.user.id}")

    return render_template("messages/new.html", form=form)


@app.get("/messages/<int:message_id>")
def messages_show(message_id):
    """Show a message."""

    msg = Message.query.get_or_404(message_id)
    return render_template("messages/show.html", message=msg)


@app.post("/messages/<int:message_id>/delete")
def messages_destroy(message_id):
    """Delete a message."""

    form = CSRFProtectForm()
    if not form.validate_on_submit():
        raise Unauthorized()

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    msg = Message.query.get_or_404(message_id)

    if msg.user_id != g.user.id:
        raise Unauthorized()

    db.session.delete(msg)
    db.session.commit()

    return redirect(f"/users/{g.user.id}")


@app.post("/messages/like/<int:message_id>")
def like_message(message_id):
    """Like a message"""

    form = CSRFProtectForm()
    if not form.validate_on_submit():
        raise Unauthorized()

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    message = Message.query.get_or_404(message_id)

    if message.user_id == g.user.id:
        flash("You can't like your own warbles!")
        return redirect(form.callback.data)

    g.user.liked_messages.append(message)
    db.session.commit()
    return redirect(form.callback.data)


@app.post("/messages/unlike/<int:message_id>")
def unlike_message(message_id):
    """Unlike a message"""

    form = CSRFProtectForm()
    if not form.validate_on_submit():
        raise Unauthorized()

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    Like.query.filter(
        Like.user_id == g.user.id, Like.message_id == message_id
    ).delete()
    db.session.commit()
    return redirect(form.callback.data)


##############################################################################
# Homepage and error pages


@app.get("/")
def homepage():
    """Show homepage:

    - anon users: no messages
    - logged in: 100 most recent messages of followed_users
    """

    if g.user:
        messages = (
            Message.query.filter(
                or_(
                    Message.user_id == g.user.id,
                    Message.user_id.in_(
                        [following.id for following in g.user.following]
                    ),
                )
            )
            .order_by(Message.timestamp.desc())
            .limit(100)
            .all()
        )

        return render_template("home.html", messages=messages)

    else:
        form = LoginForm()
        form.username.data = "demo"
        form.password.data = "123123"
        return render_template("home-anon.html", form=form)


##############################################################################
# Turn off all caching in Flask
#   (useful for dev; in production, this kind of stuff is typically
#   handled elsewhere)
#
# https://stackoverflow.com/questions/34066804/disabling-caching-in-flask


@app.after_request
def add_header(response):
    """Add non-caching headers on every request."""

    # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control
    response.cache_control.no_store = True
    return response
