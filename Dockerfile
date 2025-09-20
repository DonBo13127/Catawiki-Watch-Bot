FROM python:3.11-slim

# Installer les dépendances pour Playwright
RUN apt-get update && \
    apt-get install -y curl gnupg libnss3 libatk1.0-0 libatk-bridge2.0-0 \
    libasound2 libxcomposite1 libxdamage1 libxfixes3 libgbm1 libxkbcommon0 \
    libdbus-1-3 libatspi2.0-0 && \
    rm -rf /var/lib/apt/lists/*

# Installer Playwright et Python requirements
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install

COPY . .

CMD ["python", "main.py"]
