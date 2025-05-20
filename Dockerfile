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

# Create necessary directories with permissive permissions
RUN mkdir -p /app/data/csv /app/data/db /app/staticfiles /app/app/static \
    && chmod -R 777 /app/data

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Set permissions on data directories again after copy
RUN chmod -R 777 /app/data /app/staticfiles /app/app/static

# Expose port
EXPOSE 8000

# Run the application with root (this will be overridden by docker-compose)
CMD ["bash", "-c", "python manage.py makemigrations && python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn core.wsgi:application --bind 0.0.0.0:8000"] 