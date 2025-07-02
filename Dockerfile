# Dockerfile for Fly staging deployment with proper setup
FROM python:3.10.14-slim

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# Use gunicorn to run the app in production, using Fly.io's release_command for migrations separately
CMD ["gunicorn", "-b", "0.0.0.0:8080", "app:app"]