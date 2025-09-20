# Base image officielle Playwright pour Python
FROM mcr.microsoft.com/playwright/python:v1.37.1-focal

# Crée le répertoire de travail
WORKDIR /app

# Copier les fichiers requirements et le script
COPY requirements.txt .
COPY main.py .

# Installer les dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Installer les dépendances système nécessaires pour Playwright
RUN playwright install --with-deps

# Expose le port pour Flask
EXPOSE 8080

# Définir les variables d'environnement (tu pourras les remplacer via Render/Secrets)
# ENV GMAIL_USER=ton_mail@gmail.com
# ENV GMAIL_PASS=mot_de_passe
# ENV OPENAI_API_KEY=ta_cle_openai

# Commande pour démarrer le bot
CMD ["python", "main.py"]
