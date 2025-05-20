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

# Create app user
RUN useradd -ms /bin/bash app_user

# Create necessary directories and set permissions
RUN mkdir -p /app/data/csv /app/data/db /app/staticfiles \
    && chown -R app_user:app_user /app

# Install Python dependencies
COPY --chown=app_user:app_user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY --chown=app_user:app_user . .

# Switch to app user
USER app_user

# Expose port
EXPOSE 8000

# Run the application
CMD ["bash", "-c", "python manage.py makemigrations && python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn core.wsgi:application --bind 0.0.0.0:8000"] 