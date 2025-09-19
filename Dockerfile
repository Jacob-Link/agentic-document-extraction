# Uses Python 3.12 + Chromium + proper system deps (multi-arch incl. arm64)
FROM mcr.microsoft.com/playwright/python:v1.49.1-jammy

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DISK_DOWNLOAD_DIR=/data \
    HEADLESS=true \
    CLEAN_DOWNLOADS_AFTER=false

WORKDIR /app

# Copy and install deps
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

# Browsers are already present in this image; this is a harmless no-op:
RUN python -m playwright install chromium

# App code
COPY . /app

# Downloads dir
RUN mkdir -p /data && chmod -R 777 /data

CMD ["python", "test_simple.py"]