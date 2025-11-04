Stripe Payments, Subscriptions, Invoicing (Flask)

Features:
- One-time payments via Stripe Checkout
- Subscriptions via Stripe Checkout
- Customer Billing Portal
- Invoicing (create invoice items, finalize and optionally send)
- Refunds
- Webhook handling for key payment lifecycle events

Setup:
1) Copy .env.example to .env and fill in keys from your Stripe Dashboard.
2) Create at least one Price in Stripe (one-time for payments, recurring for subscriptions).
3) Install dependencies:
   pip install -r requirements.txt
4) Run server:
   python app.py
5) In another terminal, forward webhooks (replace port if needed):
   stripe listen --forward-to localhost:4242/webhook
   Then set STRIPE_WEBHOOK_SECRET from the output.

Test:
- Open http://localhost:4242
- Use test price IDs (price_...) and test cards (4242 4242 4242 4242, any future date, any CVC).

API Endpoints:
- POST /create-checkout-session
  Body: { price_id, quantity?, customer_id?, customer_email?, success_url?, cancel_url?, metadata? }
- POST /create-subscription-session
  Body: { price_id, quantity?, trial_period_days?, customer_id?, customer_email?, success_url?, cancel_url?, metadata? }
- POST /create-portal-session
  Body: { customer_id, return_url? }
- POST /invoices/create
  Body: { customer_id, items: [{price_id, quantity?} | {amount, currency?, description?}]..., collection_method? (send_invoice|charge_automatically), days_until_due?, currency?, auto_advance?, send_invoice?, description?, metadata? }
- POST /refunds
  Body: { payment_intent_id? | charge_id?, amount?, reason? }
- POST /webhook
  Stripe webhook endpoint. Set STRIPE_WEBHOOK_SECRET for signature verification.

Notes:
- For Checkout, pass customer_email or an existing customer_id. If neither is provided, Checkout will create a new customer when customer_creation is enabled.
- For invoicing with collection_method=send_invoice, Stripe emails the invoice to the customer when send_invoice=true.
- For refunds, pass either a payment_intent_id or charge_id. Amount is in cents; omit for a full refund.

