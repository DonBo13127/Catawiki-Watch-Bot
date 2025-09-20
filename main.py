import os
import time
import json
import threading
from datetime import timedelta
from openai import OpenAI
from playwright.sync_api import sync_playwright
import smtplib
from email.mime.text import MIMEText
import schedule
import flask

# ----------------------------
# CONFIG
# ----------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASS = os.getenv("GMAIL_PASS")
CATAWIKI_URL = "https://www.catawiki.com/en/c/333-watches"

MAX_PRICE = 2500
MIN_ESTIMATION = 5000
MAX_REMAINING_HOURS = 24
SEEN_FILE = "seen.json"

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
# GPT pour détecter champs
# ----------------------------
def detect_fields_gpt(lot_html, lot_url):
    prompt = f"""
Tu es un expert en web scraping. Voici le HTML d'un lot Catawiki :
URL: {lot_url}

{lot_html[:5000]}  # limite pour ne pas dépasser tokens

Retourne uniquement du JSON pour :
- title
- price
- estimation
- remaining (en secondes)

Si tu ne trouves pas, mets null.
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
# Scraping avec Playwright
# ----------------------------
def scrape_catawiki():
    print("\n🔍 Scraping Catawiki avec Playwright + GPT (Super Verbose)...")
    interesting_lots = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(CATAWIKI_URL)
        time.sleep(5)  # attendre chargement complet

        lots = page.query_selector_all("a.LotTile-link")
        print(f"DEBUG: Nombre de lots trouvés : {len(lots)}")

        for lot in lots:
            lot_url = lot.get_attribute("href")
            if not lot_url:
                continue
            full_url = "https://www.catawiki.com" + lot_url
            lot_id = lot_url.split("/")[-1]
            if lot_id in seen_lots:
                continue

            print(f"DEBUG: Récupération HTML du lot {lot_id} | URL: {full_url}")
            lot_html = lot.inner_html()

            processed = detect_fields_gpt(lot_html, full_url)
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
                    interesting_lots.append({"title": title, "price": price, "estimation": estimation, "remaining": remaining, "url": full_url})

            seen_lots.add(lot_id)
            time.sleep(0.3)

        browser.close()

    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen_lots), f)

    send_email(interesting_lots)

# ----------------------------
# Scheduler + Flask
# ----------------------------
app = flask.Flask(__name__)
@app.route("/")
def home():
    return "✅ Bot Catawiki + GPT actif !"

threading.Thread(target=lambda: app.run(host="0.0.0.0", port=8080)).start()

print("🚀 Bot Playwright + GPT lancé. Vérification immédiate...")
scrape_catawiki()
schedule.every().hour.do(scrape_catawiki)

while True:
    schedule.run_pending()
    time.sleep(60)
