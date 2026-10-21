FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev gcc pkg-config \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 \
    libffi-dev libcairo2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Uninstall pip after installing deps: it is not used at runtime, and its vendored
# copies of certifi/urllib3/msgpack/setuptools keep tripping the Trivy scan.
RUN pip install --no-cache-dir -r requirements.txt \
    && pip uninstall -y pip \
    && apt-get purge -y linux-libc-dev \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY . .

RUN mkdir -p /app/uploads

EXPOSE 8000

CMD ["./entrypoint.sh"]
