FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt greenlet email-validator stripe slowapi bcrypt==4.0.1 sendgrid "sentry-sdk[fastapi]"

# Free city-level GeoIP database (DB-IP Lite, CC-BY 4.0), baked into the image
# so lookups stay local: no per-request cost, no rate limits, and no third
# party receives visitor IP addresses.
#
# DB-IP publishes monthly. Falls back to last month's file if the current one
# isn't out yet, and never fails the build — a missing database just means
# /api/location/detect reports no city and the UI uses city-neutral copy.
RUN mkdir -p /app/geoip && \
    for m in $(date -u +%Y-%m) $(date -u -d '1 month ago' +%Y-%m); do \
      if curl -fsSL "https://download.db-ip.com/free/dbip-city-lite-$m.mmdb.gz" -o /tmp/geo.gz; then \
        gunzip -c /tmp/geo.gz > /app/geoip/dbip-city-lite.mmdb && rm -f /tmp/geo.gz && \
        echo "GeoIP database: dbip-city-lite-$m" && break; \
      fi; \
    done; \
    ls -lh /app/geoip/ || true

COPY . .

RUN mkdir -p uploads

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
