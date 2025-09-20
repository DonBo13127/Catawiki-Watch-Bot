import requests
from bs4 import BeautifulSoup
import smtplib
import schedule
import time
import os
from datetime import timedelta
from flask import Flask
import threading
import re
import json

# --- Config Email ---
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASS = os.getenv("GMAIL_PASS")
TO_EMAIL = os.getenv("TO_EMAIL")

# --- Liste des marques prestigieuses ---
WATCH_KEYWORDS = [
    "Rolex", "Patek", "Audemars", "Omega", "Vacheron",
    "Jaeger", "IWC", "Cartier", "Hublot", "Richard Mille"
]

# --- Fichier historique des lots vus ---
SEEN_FILE = "seen.json"
if os.path.exists(SEEN_FILE):
    with open(SEEN_FILE, "r") as f:
        seen_lots = set(json.load(f))
else:
    seen_lots = set()

# --- Serveur Flask pour UptimeRobot ---
app = Flask(__name__)
@app.route("/")
def home():
    return "✅ Bot Catawiki actif !"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

# --- Envoi email ---
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

# --- Parsing des valeurs en euro ---
def parse_euro(value_str):
    if not value_str:
        return None
    clean = re.sub(r'[^\d]', '', value_str)
    try:
        return int(clean)
    except:
        return None

# --- Récupérer détails d'un lot ---
def get_lot_details(lot_url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(lot_url, headers=headers, timeout=15)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, 'html.parser')

        title_tag = soup.find('h1')
        title = title_tag.get_text(strip=True) if title_tag else ""

        price_tag = soup.find(lambda tag: tag.name=="span" and "current bid" in tag.get_text(strip=True).lower())
        price = parse_euro(price_tag.get_text()) if price_tag else None

        time_tag = soup.find(lambda tag: tag.name=="span" and "ends in" in tag.get_text(strip=True).lower())
        remaining = None
        if time_tag:
            m = re.search(r'(?:(\d+)h)?\s*(\d+)m', time_tag.get_text(strip=True))
            if m:
                hours = int(m.group(1)) if m.group(1) else 0
                minutes = int(m.group(2))
                remaining = timedelta(hours=hours, minutes=minutes)

        return {"title": title, "url": lot_url, "price": price, "remaining": remaining}
    except Exception as e:
        print(f"Erreur récupération lot {lot_url} :", e)
        return None

# --- Scraping principal optimisé ---
def check_catawiki():
    global seen_lots
    print("🔍 Vérification des enchères Catawiki...")
    url = "https://www.catawiki.com/en/c/191-watches"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
    except Exception as e:
        print("Erreur requête:", e)
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    new_results = []

    for item in soup.find_all("a", class_="LotTile-link"):
        title_preview = item.get_text(strip=True)
        lot_url = "https://www.catawiki.com" + item.get("href")

        if not any(keyword in title_preview for keyword in WATCH_KEYWORDS):
            continue

        # Filtrer rapidement avec le prix approximatif et temps approximatif
        price_tag = item.find("span", class_="LotTile-price")
        approx_price = parse_euro(price_tag.get_text() if price_tag else "")
        time_tag = item.find("span", class_="LotTile-timeRemaining")
        approx_time = None
        if time_tag:
            m = re.search(r'(?:(\d+)h)?\s*(\d+)m', time_tag.get_text(strip=True))
            if m:
                hours = int(m.group(1)) if m.group(1) else 0
                minutes = int(m.group(2))
                approx_time = timedelta(hours=hours, minutes=minutes)

        if approx_price is None or approx_price > 3000:
            continue
        if approx_time is None or approx_time > timedelta(hours=1):
            continue

        # Ouvrir la page détail seulement si le lot est plausible
        lot = get_lot_details(lot_url)
        if not lot:
            continue
        if lot["price"] is None or lot["price"] > 3000:
            continue
        if lot["remaining"] is None or lot["remaining"] > timedelta(hours=1):
            continue

        if lot_url not in seen_lots:
            seen_lots.add(lot_url)
            new_results.append(f"{lot['title']} → {lot['url']} (Prix: €{lot['price']}, Temps restant: {lot['remaining']})")

        time.sleep(0.5)

    if new_results:
        body = "\n".join(new_results)
        send_email("⚡ Alerte Catawiki – Nouveaux lots < 3000€ proches de fin", body)
        with open(SEEN_FILE, "w") as f:
            json.dump(list(seen_lots), f)
    else:
        print("⏳ Aucune enchère intéressante trouvée cette heure-ci.")

# --- Lancer Flask dans un thread ---
threading.Thread(target=run_flask).start()

print("🚀 Bot lancé. Vérification immédiate...")

# --- Exécution immédiate ---
check_catawiki()  # <-- lance le bot dès maintenant

# --- Scheduler toutes les heures ---
schedule.every().hour.do(check_catawiki)

# --- Boucle infinie ---
while True:
    schedule.run_pending()
    time.sleep(60)
