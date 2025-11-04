# ideater: feature feat-invoices implemented

from flask import Flask
app = Flask(__name__)

# Ideater: feat-profile (in-progress)
@app.get("/profile")
def profile():
    """@ideater(feature='feat-profile', status='in-progress')"""
    return {"ok": True}

# Some unrelated code mentioning feat-login in docs only
"""
Documentation:
- ideater: feat-login (planned)
"""

@app.get("/")
def index():
    return "Hello"

