from flask import Blueprint, request, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        is_seller = True if request.form.get('is_seller') == 'on' else False
        if not email or not password:
            flash('Email and password are required.', 'error')
            return render_template('signup.html')
        existing = User.query.filter_by(email=email).first()
        if existing:
            flash('Email already registered. Please login.', 'error')
            return redirect(url_for('auth.login'))
        user = User(email=email, is_seller=is_seller)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for('marketplace.index'))
    return render_template('signup.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            next_url = request.args.get('next') or url_for('marketplace.index')
            return redirect(next_url)
        flash('Invalid credentials.', 'error')
    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('marketplace.index'))

