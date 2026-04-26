FROM python:3.13-slim

WORKDIR /app

# Bump APT_REFRESH to invalidate the GHA build cache for the apt layer when a
# Debian security update is needed (e.g., to pick up CVE-fixed system packages).
ARG APT_REFRESH=2026-04-26
RUN echo "apt refresh: $APT_REFRESH" \
    && apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev gcc pkg-config \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 \
    libffi-dev libcairo2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/uploads

EXPOSE 8000

CMD ["./entrypoint.sh"]
