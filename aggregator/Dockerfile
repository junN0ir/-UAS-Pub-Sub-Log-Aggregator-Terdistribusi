FROM python:3.11-slim

# Install curl untuk Docker healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Non-root user untuk keamanan
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

WORKDIR /app

# Install dependencies dulu (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy kode aplikasi
COPY . .

# Ganti ke non-root user
RUN chown -R appuser:appgroup /app
USER appuser

EXPOSE 8080

CMD ["python", "main.py"]