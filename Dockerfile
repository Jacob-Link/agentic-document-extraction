FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create user with home directory
RUN useradd -m app && mkdir -p /app/data && chown -R app:app /app

# Copy application and fix permissions
COPY . .
RUN chown -R app:app /app

USER app

# Install playwright browsers as non-root user
RUN playwright install chromium

ENV PYTHONPATH=/app BROWSER_HEADLESS=true

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]