# Use Python 3.11 slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create necessary directories
RUN mkdir -p /app/data/csv /app/data/db /app/staticfiles /app/app/static \
    && chown -R 1000:1000 /app \
    && chmod -R 755 /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Set proper ownership for copied files
RUN chown -R 1000:1000 /app

# Run as non-root user
USER 1000

# Expose port
EXPOSE 8000

# Run the application
CMD ["bash", "-c", "python manage.py makemigrations && python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn core.wsgi:application --bind 0.0.0.0:8000"] 