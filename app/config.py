from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Plus"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/luxe"
    DATABASE_URL_SYNC: str = "postgresql://postgres:postgres@localhost:5432/luxe"
    SECRET_KEY: str = "change-me-in-production-use-a-real-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15  # Short-lived access token
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    S3_BUCKET: str = ""
    S3_REGION: str = "us-east-1"
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PREMIUM_PRICE_ID: str = ""  # Stripe Price ID for Premium monthly
    STRIPE_DIAMOND_PRICE_ID: str = ""  # Stripe Price ID for Diamond monthly
    STRIPE_PREMIUM_ANNUAL_PRICE_ID: str = ""  # Stripe Price ID for Premium annual
    STRIPE_DIAMOND_ANNUAL_PRICE_ID: str = ""  # Stripe Price ID for Diamond annual
    FIRST_PURCHASE_COUPON_ID: str = "5LpkJfaj"  # Stripe coupon for first-month discount
    SENTRY_DSN: str = ""
    SENDGRID_API_KEY: str = ""
    RESEND_API_KEY: str = ""
    RESEND_AUDIENCE_ID: str = ""
    FROM_EMAIL: str = "noreply@meetyourplus.com"
    FRONTEND_URL: str = "http://localhost:3000"
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    ENVIRONMENT: str = "development"  # development | production
    CRON_SECRET: str = ""  # Secret for daily cron endpoint (X-Cron-Secret header)

    model_config = {"env_file": ".env"}


settings = Settings()
