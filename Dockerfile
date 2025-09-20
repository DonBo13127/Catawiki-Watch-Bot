# Base image Python officielle
FROM python:3.11-slim

# Crée le répertoire de travail
WORKDIR /app

# Copie les fichiers
COPY . /app

# Installe les dépendances
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Expose le port pour Render
EXPOSE 10000

# Commande pour lancer le bot
CMD ["python", "main.py"]
