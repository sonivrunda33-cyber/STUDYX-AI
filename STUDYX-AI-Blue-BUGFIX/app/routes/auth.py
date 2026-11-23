import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db
from ..models import PasswordResetToken, StudentProfile, User


auth = Blueprint("auth", __name__)
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def safe_next(value):
    if not value:
        return url_for("pages.workspace_dashboard")
    target = urlparse(urljoin(request.host_url, value))
    if target.scheme in {"http", "https"} and target.netloc == request.host:
        return target.path or url_for("pages.workspace_dashboard")
    return url_for("pages.workspace_dashboard")


def set_identity(user):
    session.clear()
    session.permanent = True
    session["user_id"] = user.id
    session["display_name"] = user.profile.full_name if user.profile else user.email.split("@")[0]
    session["theme_mode"] = user.profile.preferences.get("theme_mode", "light") if user.profile else "light"


@auth.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("pages.workspace_dashboard"))
    error = None
    email_value = ""
    if request.method == "POST":
        email_value = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter(db.func.lower(User.email) == email_value).first()
        if not user or not check_password_hash(user.password_hash, password):
            error = "Email and password did not match."
        elif not user.active:
            error = "This account is currently unavailable."
        else:
            if user.profile is None:
                user.profile = StudentProfile(full_name=email_value.split("@")[0])
                db.session.commit()
            set_identity(user)
            return redirect(safe_next(request.form.get("next") or request.args.get("next")))
    return render_template("auth.html", mode="login", error=error,
                           next_path=request.values.get("next", ""), email_value=email_value)


@auth.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("pages.workspace_dashboard"))
    error = None
    values = {}
    if request.method == "POST":
        name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirmation = request.form.get("confirm_password", "")
        values = {"full_name": name, "email": email}
        if not 2 <= len(name) <= 100:
            error = "Name must be between 2 and 100 characters."
        elif len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
            error = "Enter a valid email address."
        elif len(password) < 10 or len(password) > 128:
            error = "Choose a password with 10–128 characters."
        elif password != confirmation:
            error = "Those passwords do not match."
        else:
            user = User(email=email, password_hash=generate_password_hash(password, method="scrypt"))
            user.profile = StudentProfile(full_name=name)
            db.session.add(user)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                error = "An account with that email already exists."
            if not error:
                set_identity(user)
                return redirect(url_for("pages.workspace_dashboard"))
    return render_template("auth.html", mode="register", error=error, values=values)


@auth.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    message = None
    token = request.args.get("token", "").strip()
    error = None
    if request.method == "POST" and request.form.get("token"):
        token = request.form.get("token", "").strip()
        password = request.form.get("password", "")
        confirmation = request.form.get("confirm_password", "")
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        reset = PasswordResetToken.query.filter_by(token_hash=token_hash, used_at=None).first()
        expires_at = reset.expires_at.replace(tzinfo=timezone.utc) if reset and reset.expires_at.tzinfo is None else (reset.expires_at if reset else None)
        if not reset or expires_at < datetime.now(timezone.utc):
            error = "That reset link is invalid or has expired."
        elif len(password) < 10 or len(password) > 128:
            error = "Choose a password with 10–128 characters."
        elif password != confirmation:
            error = "Those passwords do not match."
        else:
            reset.user.password_hash = generate_password_hash(password, method="scrypt")
            reset.used_at = datetime.now(timezone.utc)
            db.session.commit()
            flash("Password updated. Sign in with your new password.", "success")
            return redirect(url_for("auth.login"))
    elif request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter(db.func.lower(User.email) == email).first()
        # Always show a generic confirmation so account existence is not disclosed.
        message = "If an account matches, a one-time link is ready for local development."
        if user:
            raw_token = secrets.token_urlsafe(36)
            reset = PasswordResetToken(
                user_id=user.id,
                token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
            )
            db.session.add(reset)
            db.session.commit()
            reset_url = url_for("auth.forgot_password", token=raw_token, _external=True)
            current_app.logger.warning("Local StudyX password-reset URL: %s", reset_url)
    return render_template("forgot_password.html", message=message, token=token, error=error)


@auth.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
