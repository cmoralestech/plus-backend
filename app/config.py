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
    # Everything is unlocked for everyone while we build the member base.
    #
    # Paid tiers only make sense once there are enough people in a city that a
    # free member runs out of room; charging before that sells a limit, not a
    # product. Nothing about billing is deleted — Stripe, the tiers and the
    # feature map all still exist, and flipping this back to False restores
    # them exactly as they were.
    #
    # Anything that reads this must fail OPEN: if the flag is on and the check
    # is ambiguous, grant the feature. A member who was told the app is free
    # and then hits a paywall is a worse outcome than a feature given away.
    FREE_MODE: bool = True
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
    # A profile with no visible photograph doesn't appear in discovery.
    #
    # The rule is right — a photo-first feed of blank cards reads as an empty
    # product, and it gives members the one incentive that actually improves
    # the feed. It stays off until there are photographs to show: switching it
    # on against the current data would empty discovery completely.
    REQUIRE_PHOTO_FOR_DISCOVERY: bool = False

    # How far discovery reaches when the caller doesn't specify. Miami members
    # were being shown Houston members 960 miles away — accurately labelled, and
    # a quarter of the feed. 100 covers a metro area and the drive around it
    # while keeping the two launch markets firmly separate.
    DISCOVER_DEFAULT_RADIUS_MILES: float = 100.0

    CRON_SECRET: str = ""  # Secret for daily cron endpoint (X-Cron-Secret header)

    # Automated screening of uploaded photographs. Empty provider means off, and
    # uploads are stored unscanned exactly as they were before this existed.
    # "rekognition" uses the AWS credentials already configured for S3.
    # "" (off) | "sightengine" | "rekognition"
    IMAGE_MODERATION_PROVIDER: str = ""
    # Sightengine is a plain API key — no cloud account, and its free tier has
    # no time limit, which is why it is the default choice here.
    SIGHTENGINE_API_USER: str = ""
    SIGHTENGINE_API_SECRET: str = ""
    # Rekognition needs real AWS credentials. Object storage runs on Tigris,
    # whose keys are named AWS_* but authenticate only against Tigris — so these
    # are deliberately separate and are NOT inherited from the ambient
    # environment. Leave blank only when running on genuine AWS infrastructure
    # where an instance role supplies them.
    IMAGE_MODERATION_ACCESS_KEY_ID: str = ""
    IMAGE_MODERATION_SECRET_ACCESS_KEY: str = ""
    IMAGE_MODERATION_REGION: str = "us-east-1"
    # Confidence at which a label refuses the upload outright vs. holds it for
    # human review. Rekognition is confident about explicit content and much less
    # so about suggestive content, hence the gap.
    IMAGE_MODERATION_REJECT_THRESHOLD: float = 80.0
    IMAGE_MODERATION_FLAG_THRESHOLD: float = 55.0
    IMAGE_MODERATION_TIMEOUT_SECONDS: float = 8.0
    # When a scan errors, hold the photo for review rather than publishing it.
    # Turning this off means a provider outage silently disables screening.
    IMAGE_MODERATION_FAIL_CLOSED: bool = True

    model_config = {"env_file": ".env"}


settings = Settings()
