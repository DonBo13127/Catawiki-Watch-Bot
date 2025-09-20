import os
import time
import json
import re
from datetime import timedelta
from flask import Flask
import threading
import requests
from bs4 import BeautifulSoup
import schedule
import smtplib
from email.mime.text import MIMEText
from openai import OpenAI

# ----------------------------
# CONFIG
# ----------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASS = os.getenv("GMAIL_PASS")
BASE_URL = "https://www.catawiki.com/en/c/333-watches"
SEEN_FILE = "seen.json"

MAX_PRICE = 2500
MIN_ESTIMATION = 5000
MAX_REMAINING_HOURS = 24

client = OpenAI(api_key=OPENAI_API_KEY)

# ----------------------------
# Historique lots vus
# ----------------------------
if os.path.exists(SEEN_FILE):
    with open(SEEN_FILE, "r") as f:
        seen_lots = set(json.load(f))
else:
    seen_lots = set()

# ----------------------------
# Flask pour UptimeRobot
# ----------------------------
app = Flask(__name__)
@app.route("/")
def home():
    return "✅ Bot Catawiki + GPT actif !"

threading.Thread(target=lambda: app.run(host="0.0.0.0", port=8080)).start()

# ----------------------------
# Utils
# ----------------------------
def parse_euro(value_str):
    if not value_str:
        return None
    clean = re.sub(r"[^\d]", "", value_str)
    try:
        return int(clean)
    except:
        return None

def parse_remaining(time_str):
    if not time_str:
        return None
    m = re.search(r"(?:(\d+)d)?\s*(?:(\d+)h)?\s*(\d+)m", time_str)
    if m:
        days = int(m.group(1)) if m.group(1) else 0
        hours = int(m.group(2)) if m.group(2) else 0
        minutes = int(m.group(3))
        return timedelta(days=days, hours=hours, minutes=minutes)
    return None

def send_email(lots):
    if not lots:
        print("ℹ️ Aucun lot intéressant à envoyer par mail.")
        return
    body = "🔔 Lots intéressants trouvés :\n\n"
    for lot in lots:
        body += f"{lot['title']}\nPrix: {lot['price']} | Estimation: {lot['estimation']} | Temps restant: {lot['remaining']}\nURL: {lot['url']}\n\n"

    msg = MIMEText(body)
    msg["Subject"] = "🔔 Lots Catawiki intéressants"
    msg["From"] = GMAIL_USER
    msg["To"] = GMAIL_USER

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_PASS)
        server.send_message(msg)
        server.quit()
        print("✅ Email envoyé avec succès.")
    except Exception as e:
        print("❌ Erreur envoi email :", e)

# ----------------------------
# GPT pour détecter sélecteurs
# ----------------------------
def detect_selectors_gpt(html_snippet):
    prompt = f"""
Tu es un expert en web scraping. Analyse ce HTML et retourne **uniquement du JSON** pour extraire tous les sélecteurs possibles de :
1. Le titre du lot
2. Le prix actuel
3. L'estimation
4. Le temps restant

JSON avec clés : title, price, estimation, remaining
Chaque valeur = un sélecteur CSS valide utilisable avec BeautifulSoup select_one
Si plusieurs options existent, donne-les toutes sous forme de liste
Retourne uniquement du JSON, sans explications
HTML COMPLET : {html_snippet}
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        selectors_json = response.choices[0].message.content
        try:
            selectors = json.loads(selectors_json)
        except json.JSONDecodeError:
            print("❌ JSON GPT invalide :", selectors_json)
            return None
        return selectors
    except Exception as e:
        print("❌ Erreur GPT :", e)
        return None

# ----------------------------
# Scraping d'un lot
# ----------------------------
def scrape_lot(lot_url, selectors):
    try:
        r = requests.get(lot_url)
        soup = BeautifulSoup(r.text, "html.parser")

        def extract_first(tag):
            if isinstance(tag, list):
                for t in tag:
                    el = soup.select_one(t)
                    if el:
                        return el.get_text(strip=True)
                return None
            elif isinstance(tag, str):
                el = soup.select_one(tag)
                return el.get_text(strip=True) if el else None
            return None

        title = extract_first(selectors.get("title", [])) or "N/A"
        price = parse_euro(extract_first(selectors.get("price", [])))
        estimation = parse_euro(extract_first(selectors.get("estimation", [])))
        remaining = parse_remaining(extract_first(selectors.get("remaining", [])))

        print(f"DEBUG LOT: {title} | Prix: {price} | Estimation: {estimation} | Temps restant: {remaining}")
        print(f"DEBUG LOT HTML (limité 500 chars): {r.text[:500]}")

        return {"title": title, "url": lot_url, "price": price, "estimation": estimation, "remaining": remaining}

    except Exception as e:
        print(f"❌ Erreur scraping lot {lot_url} :", e)
        return None

# ----------------------------
# Scraping page principale (optimisé)
# ----------------------------
def scrape_catawiki():
    print("\n🔍 Scraping Catawiki (optimisé + logs détaillés)...")
    r = requests.get(BASE_URL)
    soup = BeautifulSoup(r.text, "html.parser")

    # GPT détecte les sélecteurs depuis la page principale
    html_snippet = r.text[:3000]
    selectors = detect_selectors_gpt(html_snippet)
    if not selectors:
        print("⚠️ GPT n'a trouvé aucun sélecteur !")
        return

    print("DEBUG Sélecteurs GPT :", json.dumps(selectors, indent=2))

    items = soup.select("a.LotTile-link")
    print("DEBUG: Nombre de lots trouvés :", len(items))

    interesting_lots = []

    for item in items:
        lot_url = item.get("href")
        if lot_url.startswith("/"):
            lot_url = "https://www.catawiki.com" + lot_url
        if lot_url in seen_lots:
            continue

        # Scrape minimal depuis la page principale si possible
        soup_item = item
        def extract_first(tag):
            if isinstance(tag, list):
                for t in tag:
                    el = soup_item.select_one(t)
                    if el:
                        return el.get_text(strip=True)
                return None
            elif isinstance(tag, str):
                el = soup_item.select_one(tag)
                return el.get_text(strip=True) if el else None
            return None

        price = parse_euro(extract_first(selectors.get("price", [])))
        estimation = parse_euro(extract_first(selectors.get("estimation", [])))
        remaining = parse_remaining(extract_first(selectors.get("remaining", [])))

        if price and estimation and remaining:
            if price <= MAX_PRICE and estimation >= MIN_ESTIMATION and remaining.total_seconds() <= MAX_REMAINING_HOURS*3600:
                lot = scrape_lot(lot_url, selectors)
                if lot:
                    interesting_lots.append(lot)

        seen_lots.add(lot_url)
        time.sleep(0.3)

    # Sauvegarde des lots vus
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen_lots), f)

    send_email(interesting_lots)

# ----------------------------
# Execution
# ----------------------------
print("🚀 Bot Catawiki + GPT optimisé et super verbose lancé. Vérification immédiate...")
scrape_catawiki()
schedule.every().hour.do(scrape_catawiki)

while True:
    schedule.run_pending()
    time.sleep(60)
