from datetime import timedelta
from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.exc import IntegrityError
from email_validator import validate_email, EmailNotValidError
from ..extensions import db
from ..models import User, Profile, Role, EmailVerificationToken, PasswordResetToken
from ..utils import generate_token_pair, verify_token_hash, send_email, build_external_url, json_required, now_utc

auth_bp = Blueprint('auth', __name__)


def get_or_create_role(name: str, description: str | None = None) -> Role:
    role = Role.query.filter_by(name=name).first()
    if not role:
        role = Role(name=name, description=description or name)
        db.session.add(role)
        db.session.commit()
    return role


@auth_bp.post('/register')
@json_required(['email', 'password'])
def register():
    data = request.get_json()
    raw_email = data.get('email', '').strip()
    try:
        v = validate_email(raw_email)
        email = v.email.lower()
    except EmailNotValidError as e:
        return jsonify({"error": str(e)}), 400

    password = data.get('password', '')
    if not isinstance(password, str) or len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 400

    user = User(email=email)
    user.set_password(password)

    profile = Profile(
        user=user,
        full_name=data.get('full_name'),
        bio=data.get('bio'),
        avatar_url=data.get('avatar_url'),
        phone=data.get('phone'),
        timezone=data.get('timezone'),
    )

    db.session.add(user)
    db.session.add(profile)

    # Ensure base roles exist
    user_role = get_or_create_role('user', 'Default user role')
    user.roles.append(user_role)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Registration failed"}), 400

    send_verification_email(user, target_email=email)

    return jsonify({"message": "Registration successful. Please verify your email.", "user": user.to_dict()}), 201


def send_verification_email(user: User, target_email: str):
    token_plain, token_hash = generate_token_pair()
    expires = now_utc() + timedelta(hours=int(auth_bp.current_app.config.get('SECURITY_EMAIL_TOKEN_HOURS', 48)))
    evt = EmailVerificationToken(user_id=user.id, token_hash=token_hash, email_to_verify=target_email.lower(), expires_at=expires)
    db.session.add(evt)
    db.session.commit()
    composite = f"{evt.id}.{token_plain}"

    verify_url = build_external_url(f"/auth/verify-email?token={composite}")

    subject = "Verify your email"
    text = f"Hello,\n\nPlease verify your email by clicking the link below:\n{verify_url}\n\nIf you did not sign up, you can ignore this message."
    html = f"<p>Hello,</p><p>Please verify your email by clicking the link below:</p><p><a href='{verify_url}'>{verify_url}</a></p><p>If you did not sign up, you can ignore this message.</p>"

    send_email(subject, [target_email], html_body=html, text_body=text)


@auth_bp.post('/login')
@json_required(['email', 'password'])
def login():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid credentials"}), 401
    if not user.is_active:
        return jsonify({"error": "Account disabled"}), 403

    login_user(user, remember=True)
    return jsonify({"message": "Logged in", "user": user.to_dict()})


@auth_bp.post('/logout')
@login_required
def logout():
    logout_user()
    return jsonify({"message": "Logged out"})


@auth_bp.get('/me')
@login_required
def me():
    return jsonify({"user": current_user.to_dict()})


@auth_bp.post('/request-email-verification')
def request_email_verification():
    # Accepts optional email, otherwise uses current_user
    target_email = None
    if request.is_json:
        data = request.get_json(silent=True) or {}
        target_email = (data.get('email') or '').strip().lower() or None

    user = None
    if current_user.is_authenticated and current_user.is_active:
        user = current_user
        target_email = target_email or user.email
    elif target_email:
        user = User.query.filter_by(email=target_email).first()

    # Always respond success to avoid account enumeration
    if user:
        send_verification_email(user, target_email=target_email)
    return jsonify({"message": "If an account exists, a verification email has been sent."})


@auth_bp.get('/verify-email')
def verify_email():
    composite = request.args.get('token', '')
    if '.' not in composite:
        return jsonify({"error": "Invalid token"}), 400
    token_id, token_plain = composite.split('.', 1)
    evt = EmailVerificationToken.query.get(int(token_id))
    if not evt or evt.used:
        return jsonify({"error": "Invalid or used token"}), 400
    if evt.expires_at < now_utc():
        return jsonify({"error": "Token expired"}), 400
    if not verify_token_hash(token_plain, evt.token_hash):
        return jsonify({"error": "Invalid token"}), 400

    user = evt.user
    # Update email if necessary and mark verified
    if user.email != evt.email_to_verify:
        # Ensure email not taken
        if User.query.filter(User.email == evt.email_to_verify, User.id != user.id).first():
            return jsonify({"error": "Email already in use"}), 400
        user.email = evt.email_to_verify
    user.is_email_verified = True
    evt.used = True
    db.session.commit()

    return jsonify({"message": "Email verified successfully"})


@auth_bp.post('/request-password-reset')
@json_required(['email'])
def request_password_reset():
    data = request.get_json()
    raw_email = data.get('email', '').strip().lower()
    user = User.query.filter_by(email=raw_email).first()

    # Always return success
    if user and user.is_active:
        token_plain, token_hash = generate_token_pair()
        expires = now_utc() + timedelta(hours=int(auth_bp.current_app.config.get('SECURITY_RESET_TOKEN_HOURS', 2)))
        prt = PasswordResetToken(user_id=user.id, token_hash=token_hash, expires_at=expires)
        db.session.add(prt)
        db.session.commit()
        composite = f"{prt.id}.{token_plain}"

        reset_url = build_external_url(f"/auth/reset-password?token={composite}")

        subject = "Reset your password"
        text = f"Hello,\n\nUse the link below to reset your password:\n{reset_url}\n\nIf you did not request this, ignore this message."
        html = f"<p>Hello,</p><p>Use the link below to reset your password:</p><p><a href='{reset_url}'>{reset_url}</a></p><p>If you did not request this, ignore this message.</p>"
        send_email(subject, [user.email], html_body=html, text_body=text)

    return jsonify({"message": "If an account exists, a reset email has been sent."})


@auth_bp.post('/reset-password')
@json_required(['token', 'new_password'])
def reset_password():
    data = request.get_json()
    composite = data.get('token', '')
    new_password = data.get('new_password', '')

    if not isinstance(new_password, str) or len(new_password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    if '.' not in composite:
        return jsonify({"error": "Invalid token"}), 400
    token_id, token_plain = composite.split('.', 1)
    prt = PasswordResetToken.query.get(int(token_id))
    if not prt or prt.used:
        return jsonify({"error": "Invalid or used token"}), 400
    if prt.expires_at < now_utc():
        return jsonify({"error": "Token expired"}), 400
    if not verify_token_hash(token_plain, prt.token_hash):
        return jsonify({"error": "Invalid token"}), 400

    user = prt.user
    if not user.is_active:
        return jsonify({"error": "Account disabled"}), 400

    user.set_password(new_password)
    prt.used = True
    db.session.commit()

    return jsonify({"message": "Password has been reset"})

