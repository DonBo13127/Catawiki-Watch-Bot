import requests
from bs4 import BeautifulSoup
import smtplib
import schedule
import time
import os
from flask import Flask
import threading

# Configuration des emails via variables d'environnement Replit
GMAIL_USER = os.getenv("GMAIL_USER")  # ton email Gmail
GMAIL_PASS = os.getenv("GMAIL_PASS")  # ton mot de passe d'application Gmail
TO_EMAIL = os.getenv("TO_EMAIL")      # email destinataire

# --- Serveur Flask pour garder le bot actif (UptimeRobot) ---
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Bot Catawiki actif !"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

# --- Fonction d'envoi d'email ---
def send_email(subject, body):
    try:
        message = f"Subject: {subject}\n\n{body}"
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_PASS)
        server.sendmail(GMAIL_USER, TO_EMAIL, message)
        server.quit()
        print("✅ Email envoyé avec succès !")
    except Exception as e:
        print("❌ Erreur lors de l'envoi de l'email :", e)

# --- Scraping Catawiki ---
def check_catawiki():
    print("🔍 Vérification des enchères Catawiki...")
    url = "https://www.catawiki.com/en/c/191-watches"
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(response.text, 'html.parser')

    results = []

    # Exemple simple : recherche des titres et liens (à adapter au HTML réel)
    for item in soup.find_all("a", class_="LotTile-link"):
        title = item.get_text(strip=True)
        link = "https://www.catawiki.com" + item.get("href")

        # --- Ici tu dois parser les prix + temps restant ---
        # Simulation : on prend uniquement les marques prestigieuses
        if any(keyword in title for keyword in ["Rolex", "Patek", "Audemars", "Omega", "Vacheron"]):
            results.append(f"{title} → {link}")

    if results:
        body = "\n".join(results)
        send_email("⚡ Alerte Catawiki – Montres < 3000€ proches de fin", body)
    else:
        print("⏳ Aucune enchère intéressante trouvée cette heure-ci.")

# --- Planification toutes les heures ---
schedule.every().hour.do(check_catawiki)

print("🚀 Bot lancé. Vérification toutes les heures...")

# --- Lancer Flask dans un thread séparé ---
threading.Thread(target=run_flask).start()

# --- Boucle infinie pour le scheduler ---
while True:
    schedule.run_pending()
    time.sleep(60)
