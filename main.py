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
import openai

# --- Config Email et GPT ---
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASS = os.getenv("GMAIL_PASS")
TO_EMAIL = os.getenv("TO_EMAIL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# --- Historique des lots vus ---
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
    return "✅ Bot Catawiki + GPT actif !"

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

# --- Utiliser GPT pour détecter les bons sélecteurs ---
def get_selectors_with_gpt(html_snippet):
    prompt = f"""
    Analyse ce HTML et retourne les sélecteurs CSS pour extraire :
    - titre
    - prix actuel
    - estimation
    - temps restant
    Renvoie uniquement du JSON.
    HTML : {html_snippet[:2000]}...
    """
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role":"user","content":prompt}],
            temperature=0
        )
        selectors_json = response['choices'][0]['message']['content']
        selectors = json.loads(selectors_json)
        return selectors
    except Exception as e:
        print("❌ Erreur GPT :", e)
        return None

# --- Récupérer détails d'un lot avec GPT ---
def get_lot_details(lot_url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(lot_url, headers=headers, timeout=15)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, 'html.parser')
        html_snippet = str(soup)[:2000]

        # Obtenir sélecteurs via GPT
        selectors = get_selectors_with_gpt(html_snippet)
        if not selectors:
            return None

        # Extraire infos avec les sélecteurs
        title_tag = soup.select_one(selectors.get("title",""))
        title = title_tag.get_text(strip=True) if title_tag else ""

        price_tag = soup.select_one(selectors.get("price",""))
        price = parse_euro(price_tag.get_text()) if price_tag else None

        est_tag = soup.select_one(selectors.get("estimation",""))
        estimation = parse_euro(est_tag.get_text()) if est_tag else None

        time_tag = soup.select_one(selectors.get("remaining",""))
        remaining = None
        if time_tag:
            m = re.search(r'(?:(\d+)h)?\s*(\d+)m', time_tag.get_text(strip=True))
            if m:
                hours = int(m.group(1)) if m.group(1) else 0
                minutes = int(m.group(2))
                remaining = timedelta(hours=hours, minutes=minutes)

        print(f"DEBUG: {title} | Prix: {price} | Estimation: {estimation} | Temps restant: {remaining}")
        return {"title": title, "url": lot_url, "price": price, "estimation": estimation, "remaining": remaining}
    except Exception as e:
        print(f"Erreur récupération lot {lot_url} :", e)
        return None

# --- Scraping principal ---
def check_catawiki():
    global seen_lots
    print("🔍 Vérification des enchères Catawiki + GPT...")
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
        lot_url = "https://www.catawiki.com" + item.get("href")
        lot = get_lot_details(lot_url)
        if not lot:
            continue

        if lot["price"] is None or lot["price"] > 2500:
            continue
        if lot["estimation"] is None or lot["estimation"] < 5000:
            continue
        if lot["remaining"] is None or lot["remaining"] > timedelta(hours=5):
            continue

        if lot_url not in seen_lots:
            seen_lots.add(lot_url)
            new_results.append(f"{lot['title']} → {lot['url']} (Prix: €{lot['price']}, Estimation: €{lot['estimation']}, Temps restant: {lot['remaining']})")
        time.sleep(0.5)

    if new_results:
        body = "\n".join(new_results)
        send_email("⚡ Alerte Catawiki – Lots sous-évalués ≤2500€", body)
        with open(SEEN_FILE, "w") as f:
            json.dump(list(seen_lots), f)
    else:
        print("⏳ Aucune enchère intéressante trouvée cette vérification.")

# --- Lancer Flask dans un thread ---
threading.Thread(target=run_flask).start()

print("🚀 Bot lancé. Vérification immédiate...")

# --- Exécution immédiate ---
check_catawiki()

# --- Scheduler toutes les heures ---
schedule.every().hour.do(check_catawiki)

# --- Boucle infinie ---
while True:
    schedule.run_pending()
    time.sleep(60)
