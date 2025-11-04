from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user, logout_user
from email_validator import validate_email, EmailNotValidError
from ..extensions import db
from ..models import Profile, User
from ..utils import json_required

account_bp = Blueprint('account', __name__)


@account_bp.get('/profile')
@login_required
def get_profile():
    profile = current_user.profile
    if not profile:
        profile = Profile(user=current_user)
        db.session.add(profile)
        db.session.commit()
    return jsonify({"profile": profile.to_dict(), "user": current_user.to_dict(include_profile=True)})


@account_bp.put('/profile')
@login_required
def update_profile():
    data = request.get_json(silent=True) or {}
    profile = current_user.profile or Profile(user=current_user)
    for f in ['full_name', 'bio', 'avatar_url', 'phone', 'timezone']:
        if f in data:
            setattr(profile, f, data.get(f))
    db.session.add(profile)
    db.session.commit()
    return jsonify({"message": "Profile updated", "profile": profile.to_dict()})


@account_bp.put('/password')
@login_required
@json_required(['current_password', 'new_password'])
def change_password():
    data = request.get_json()
    current = data.get('current_password')
    new = data.get('new_password')

    if not current_user.check_password(current):
        return jsonify({"error": "Current password is incorrect"}), 400
    if not isinstance(new, str) or len(new) < 8:
        return jsonify({"error": "New password must be at least 8 characters"}), 400

    current_user.set_password(new)
    db.session.commit()
    return jsonify({"message": "Password changed"})


@account_bp.put('/email')
@login_required
@json_required(['new_email'])
def change_email_request():
    data = request.get_json()
    try:
        new_email = validate_email(data.get('new_email', '').strip()).email.lower()
    except EmailNotValidError as e:
        return jsonify({"error": str(e)}), 400

    # Do not change immediately; send verification to new email
    from ..auth.routes import send_verification_email

    if User.query.filter(User.email == new_email, User.id != current_user.id).first():
        return jsonify({"error": "Email already in use"}), 400

    send_verification_email(current_user, target_email=new_email)
    return jsonify({"message": "Verification email sent to new address. Please verify to complete the change."})


@account_bp.delete('')
@login_required
def delete_account():
    # Soft deactivate account and log out
    current_user.is_active = False
    db.session.commit()
    logout_user()
    return jsonify({"message": "Account deactivated"})

