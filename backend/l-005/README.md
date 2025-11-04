Blueprint Marketplace (Flask)

Features:
- Template/blueprint marketplace
- Versioning per template
- Monetization with Stripe Checkout (optional) or simulated payments
- User auth, seller dashboard, purchases, license verification endpoint

Quickstart:
1) python3 -m venv .venv && source .venv/bin/activate
2) pip install -r requirements.txt
3) cp .env.example .env  # set BASE_URL and STRIPE keys if desired
4) python app.py  # first run creates DB tables automatically

CLI:
- flask --app app.py db-create
- flask --app app.py create-user

Notes:
- Uploads are stored under ./uploads/templates/<template_id>/
- Allowed file types: .zip, .json, .yaml, .yml, .txt
- Purchases grant access to all versions of a template
- License verify: GET /license/verify?key=LICENSE_KEY&template_id=ID

