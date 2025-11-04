import os


class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "change-me")

    # Stripe
    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

    # PayPal
    PAYPAL_ENV = os.getenv("PAYPAL_ENV", "sandbox").lower()  # sandbox|live
    PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "")
    PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET", "")
    PAYPAL_WEBHOOK_ID = os.getenv("PAYPAL_WEBHOOK_ID", "")  # The Webhook ID from PayPal dashboard

    @property
    def PAYPAL_API_BASE(self) -> str:
        if self.PAYPAL_ENV == "live":
            return "https://api-m.paypal.com"
        return "https://api-m.sandbox.paypal.com"


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


def get_config():
    env = os.getenv("FLASK_ENV", "development").lower()
    if env == "production":
        return ProductionConfig()
    return DevelopmentConfig()

