FROM python:3.11-slim

# Installer toutes les dépendances nécessaires pour Playwright
RUN apt-get update && apt-get install -y \
    curl gnupg libnss3 libatk1.0-0 libatk-bridge2.0-0 \
    libasound2 libxcomposite1 libxdamage1 libxfixes3 \
    libgbm1 libxkbcommon0 libdbus-1-3 libatspi2.0-0 \
    libxrandr2 libxrender1 libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Définir le répertoire de travail
WORKDIR /app

# Copier et installer les dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Installer les navigateurs Playwright
RUN playwright install

# Copier le code
COPY . .

# Lancer le bot
CMD ["python", "main.py"]
