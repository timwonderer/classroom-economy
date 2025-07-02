FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt requirements.txt
# Pin versions in requirements.txt for consistent builds and reliability
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# Run migrations on start
CMD ["flask", "db", "upgrade"]