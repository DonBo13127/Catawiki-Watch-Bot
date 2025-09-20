import os
import time
import json
from datetime import timedelta
import threading
import requests
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
BASE_API_URL = "https://www.catawiki.com/api/v1/lots?category=333&sort=end_time&order=asc&page=1"

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
# Utils
# ----------------------------
def parse_euro(value_str):
    if not value_str:
        return None
    clean = ''.join(c for c in value_str if c.isdigit())
    try:
        return int(clean)
    except:
        return None

def parse_remaining(seconds):
    return timedelta(seconds=seconds)

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
# GPT pour confirmer sélecteurs
# ----------------------------
def detect_selectors_gpt(lot_json):
    prompt = f"""
Tu es un expert en web scraping. Analyse ce JSON de lot Catawiki et retourne **uniquement du JSON** pour les champs :
- title
- price
- estimation
- remaining (en secondes)

JSON exemple :
{json.dumps(lot_json, indent=2)}
Retourne uniquement du JSON, sans explications.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        selectors_json = response.choices[0].message.content
        try:
            data = json.loads(selectors_json)
        except json.JSONDecodeError:
            print("❌ JSON GPT invalide :", selectors_json)
            return None
        return data
    except Exception as e:
        print("❌ Erreur GPT :", e)
        return None

# ----------------------------
# Scraping page API
# ----------------------------
def scrape_catawiki():
    print("\n🔍 Scraping Catawiki API (optimisé + logs détaillés)...")
    response = requests.get(BASE_API_URL)
    if response.status_code != 200:
        print("❌ Erreur récupération API :", response.status_code)
        return

    data = response.json()
    items = data.get("lots", [])
    print("DEBUG: Nombre de lots récupérés via API :", len(items))

    interesting_lots = []

    for lot in items:
        lot_id = lot.get("id")
        if lot_id in seen_lots:
            continue

        lot_url = "https://www.catawiki.com" + lot.get("url", "")
        print(f"DEBUG: Analyse lot {lot_id} | URL: {lot_url}")

        processed = detect_selectors_gpt(lot)
        if not processed:
            print("⚠️ GPT n'a trouvé aucun champ pour ce lot.")
            seen_lots.add(lot_id)
            continue

        title = processed.get("title", "N/A")
        price = parse_euro(str(processed.get("price", 0)))
        estimation = parse_euro(str(processed.get("estimation", 0)))
        remaining = parse_remaining(int(processed.get("remaining", 0)))

        print(f"DEBUG LOT: {title} | Prix: {price} | Estimation: {estimation} | Temps restant: {remaining}")

        if price and estimation and remaining:
            if price <= MAX_PRICE and estimation >= MIN_ESTIMATION and remaining.total_seconds() <= MAX_REMAINING_HOURS*3600:
                interesting_lots.append({"title": title, "price": price, "estimation": estimation, "remaining": remaining, "url": lot_url})

        seen_lots.add(lot_id)
        time.sleep(0.3)

    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen_lots), f)

    send_email(interesting_lots)

# ----------------------------
# Scheduler
# ----------------------------
import flask
app = flask.Flask(__name__)
@app.route("/")
def home():
    return "✅ Bot Catawiki + GPT actif !"

threading.Thread(target=lambda: app.run(host="0.0.0.0", port=8080)).start()

print("🚀 Bot Catawiki + GPT optimisé lancé. Vérification immédiate...")
scrape_catawiki()
schedule.every().hour.do(scrape_catawiki)

while True:
    schedule.run_pending()
    time.sleep(60)
