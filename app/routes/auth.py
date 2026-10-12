import random
from datetime import date, datetime, timedelta

from flask import (
    Blueprint, redirect, request, session, render_template,
    flash, url_for
)
from werkzeug.security import generate_password_hash, check_password_hash

from app import db
from app.models import User, EmailOTP
from app.utils.emailer import send_otp
from app.utils.achievements import check_and_award

auth_bp = Blueprint("auth", __name__)

OTP_TTL_MINUTES = 10


def _new_otp():
    return f"{random.randint(0, 999999):06d}"


def _create_otp(email):
    """Invalidate old OTPs for this email and create a fresh one."""
    EmailOTP.query.filter_by(email=email).delete()
    code = _new_otp()
    db.session.add(EmailOTP(
        email=email,
        code=code,
        expires_at=datetime.utcnow() + timedelta(minutes=OTP_TTL_MINUTES),
    ))
    db.session.commit()
    return code


@auth_bp.route("/")
def home():
    return render_template("home.html")


# ------------------------------------------------------------------
# REGISTER — still requires email OTP
# ------------------------------------------------------------------
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        email    = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        if not username or not email or not password:
            flash("Please fill in every field.", "danger")
            return redirect(url_for("auth.register"))

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
            return redirect(url_for("auth.register"))

        if User.query.filter_by(email=email).first():
            flash("Email already exists!", "danger")
            return redirect(url_for("auth.register"))

        if User.query.filter_by(username=username).first():
            flash("Username already exists!", "danger")
            return redirect(url_for("auth.register"))

        code = _create_otp(email)

        session["pending"] = {
            "username": username,
            "email": email,
            "password_hash": generate_password_hash(password),
        }

        send_otp(email, code)
        flash(f"A 6-digit code was sent to {email}.", "info")
        return redirect(url_for("auth.verify_otp"))

    return render_template("register.html")


@auth_bp.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    pending = session.get("pending")
    if not pending:
        flash("Please register first.", "danger")
        return redirect(url_for("auth.register"))

    if request.method == "POST":
        code = (request.form.get("code") or "").strip()

        otp = (
            EmailOTP.query
            .filter_by(email=pending["email"], code=code)
            .order_by(EmailOTP.id.desc())
            .first()
        )

        if not otp or otp.expires_at < datetime.utcnow():
            flash("Invalid or expired code. Try again.", "danger")
            return redirect(url_for("auth.verify_otp"))

        new_user = User(
            username=pending["username"],
            email=pending["email"],
            password=pending["password_hash"],
        )
        db.session.add(new_user)
        db.session.delete(otp)
        db.session.commit()

        session.pop("pending", None)
        flash("Account verified! Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("verify_otp.html", email=pending["email"])


@auth_bp.route("/resend-otp", methods=["POST"])
def resend_otp():
    pending = session.get("pending")
    if not pending:
        return redirect(url_for("auth.register"))

    code = _create_otp(pending["email"])
    send_otp(pending["email"], code)
    flash("A new code has been sent.", "info")
    return redirect(url_for("auth.verify_otp"))


@auth_bp.route("/cancel-registration", methods=["POST"])
def cancel_registration():
    session.pop("pending", None)
    flash("Registration cancelled.", "info")
    return redirect(url_for("auth.register"))


# ------------------------------------------------------------------
# LOGIN — direct, no OTP
# ------------------------------------------------------------------
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            today = date.today()

            # Streak logic
            if user.last_login is None:
                user.streak = 1
            elif user.last_login == (today - timedelta(days=1)):
                user.streak += 1
            elif user.last_login == today:
                pass
            else:
                user.streak = 1

            user.last_login = today
            db.session.commit()

            # Log the user in immediately — no OTP
            session["user"] = user.id

            # Streak-based achievements can unlock on login
            newly = check_and_award(user)
            for a in newly:
                flash(f"{a['icon']} Achievement unlocked — {a['name']}", "success")

            flash("Login successful!", "success")
            return redirect(url_for("task.dashboard"))

        flash("Invalid Username or Password!", "danger")

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    session.pop("user", None)
    flash("Logged out successfully!", "info")
    return redirect(url_for("auth.login"))
# ------------------------------------------------------------------
# FORGOT PASSWORD FLOW
# ------------------------------------------------------------------
@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()

        if not email:
            flash("Please enter your email.", "danger")
            return redirect(url_for("auth.forgot_password"))

        user = User.query.filter_by(email=email).first()
        if not user:
            # Don't reveal whether the email exists — just show a generic message
            flash("If that email is registered, a code has been sent.", "info")
            return redirect(url_for("auth.verify_reset_otp"))

        # Create + send OTP
        code = _create_otp(email)
        send_otp(email, code)

        session["reset_email"] = email
        session.pop("reset_verified", None)

        # Mask for display
        name, _, domain = email.partition("@")
        masked = (name[:2] + "***@" + domain) if len(name) > 2 else ("***@" + domain)

        flash(f"A 6-digit code was sent to {masked}.", "info")
        return redirect(url_for("auth.verify_reset_otp"))

    return render_template("forgot_password.html")


@auth_bp.route("/verify-reset-otp", methods=["GET", "POST"])
def verify_reset_otp():
    email = session.get("reset_email")
    if not email:
        flash("Please enter your email first.", "danger")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        code = (request.form.get("code") or "").strip()

        otp = (
            EmailOTP.query
            .filter_by(email=email, code=code)
            .order_by(EmailOTP.id.desc())
            .first()
        )

        if not otp or otp.expires_at < datetime.utcnow():
            flash("Invalid or expired code. Try again.", "danger")
            return redirect(url_for("auth.verify_reset_otp"))

        # Consume OTP and mark session as verified
        db.session.delete(otp)
        db.session.commit()

        session["reset_verified"] = True
        flash("Code verified! Set your new password.", "success")
        return redirect(url_for("auth.reset_password"))

    # Mask for display
    name, _, domain = email.partition("@")
    masked = (name[:2] + "***@" + domain) if len(name) > 2 else ("***@" + domain)
    return render_template("verify_reset_otp.html", email=masked)


@auth_bp.route("/resend-reset-otp", methods=["POST"])
def resend_reset_otp():
    email = session.get("reset_email")
    if not email:
        return redirect(url_for("auth.forgot_password"))

    code = _create_otp(email)
    send_otp(email, code)
    flash("A new code has been sent.", "info")
    return redirect(url_for("auth.verify_reset_otp"))


@auth_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    email = session.get("reset_email")
    verified = session.get("reset_verified")

    if not email or not verified:
        flash("Please verify your email first.", "danger")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
            return redirect(url_for("auth.reset_password"))

        if password != confirm:
            flash("Passwords don't match.", "danger")
            return redirect(url_for("auth.reset_password"))

        user = User.query.filter_by(email=email).first()
        if not user:
            flash("Account not found.", "danger")
            return redirect(url_for("auth.forgot_password"))

        user.password = generate_password_hash(password)
        db.session.commit()

        # Clear reset session keys
        session.pop("reset_email", None)
        session.pop("reset_verified", None)

        flash("Password updated! Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("reset_password.html")


@auth_bp.route("/cancel-reset", methods=["POST"])
def cancel_reset():
    session.pop("reset_email", None)
    session.pop("reset_verified", None)
    flash("Password reset cancelled.", "info")
    return redirect(url_for("auth.login"))