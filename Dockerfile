# 18&ok LLC platform worker
FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for better layer caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY . .

# Background worker entry point (matches the Python services' start command)
CMD ["python", "main.py"]
