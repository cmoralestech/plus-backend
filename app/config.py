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
    # Stripe enabled Managed Payments on the account, which requires a tax code
    # on every product. Without one it rejects the session outright, so
    # checkout returned 500 and nobody could subscribe. Opted out until tax
    # codes are set on the Plus and Plus+ products, then flip this to true to
    # get the broader set of payment methods back.
    STRIPE_MANAGED_PAYMENTS: bool = False
    STRIPE_PLUS_PRICE_ID: str = ""  # Stripe Price ID for Plus monthly ($49.99)
    STRIPE_PLUS_PLUS_PRICE_ID: str = ""  # Stripe Price ID for Plus+ monthly ($99.99)
    STRIPE_PLUS_ANNUAL_PRICE_ID: str = ""  # Stripe Price ID for Plus annual ($499)
    STRIPE_PLUS_PLUS_ANNUAL_PRICE_ID: str = ""  # Stripe Price ID for Plus+ annual ($999)
    FIRST_PURCHASE_COUPON_ID: str = "5LpkJfaj"  # Stripe coupon for first-month discount
    SENTRY_DSN: str = ""
    SENDGRID_API_KEY: str = ""
    RESEND_API_KEY: str = ""
    RESEND_AUDIENCE_ID: str = ""
    FROM_EMAIL: str = "noreply@meetyourplus.com"
    FRONTEND_URL: str = "http://localhost:3000"
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    ENVIRONMENT: str = "development"  # development | production
    # Local city-level GeoIP database, baked into the image by the Dockerfile.
    # Preferred over any remote lookup: no cost, no rate limit, and visitor IPs
    # never leave our infrastructure.
    GEOIP_DB_PATH: str = "/app/geoip/dbip-city-lite.mmdb"
    # Optional remote fallback if the bundled database is unavailable. Must
    # contain "{ip}". With neither configured, /api/location/detect reports no
    # city and the UI falls back to city-neutral copy rather than guessing.
    GEOIP_LOOKUP_URL: str = ""
    GEOIP_CITY_FIELD: str = "city"
    # How far from a launch city still counts as that market. A business call,
    # not a technical one: 35mi covers Coral Gables, Hialeah, Fort Lauderdale,
    # Sugar Land, and The Woodlands, while leaving out Boca Raton (~43mi).
    ACTIVE_MARKET_RADIUS_MILES: float = 35.0

    # Financial qualification. Configurable rather than hard-coded into
    # onboarding so the bar can move without a release. A member qualifies on
    # income OR net worth — assets alone are enough, since founders and
    # investors often hold substantial assets against a modest salary.
    VERIFICATION_MIN_INCOME_USD: int = 250_000
    VERIFICATION_MIN_NET_WORTH_USD: int = 1_000_000
    # Financial standing changes; verification lapses and is asked for again.
    VERIFICATION_VALIDITY_DAYS: int = 365
    # Identity/financial verification provider. Empty means unconfigured, in
    # which case checks are recorded as pending and nothing is fabricated.
    VERIFICATION_PROVIDER: str = ""
    VERIFICATION_PROVIDER_API_KEY: str = ""
    VERIFICATION_WEBHOOK_SECRET: str = ""
    CRON_SECRET: str = ""  # Secret for daily cron endpoint (X-Cron-Secret header)

    model_config = {"env_file": ".env"}


settings = Settings()
