FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY wifi_notifier.py .
COPY aterm_scraper.py .

# Create volume mount point for config
VOLUME /config

# Run the application
CMD ["python", "wifi_notifier.py", "/config/config.json"]
