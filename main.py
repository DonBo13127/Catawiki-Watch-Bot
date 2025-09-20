import os
import time
import json
import re
import requests
from datetime import timedelta
from flask import Flask
import threading
import openai
from bs4 import BeautifulSoup
import schedule

# --- Config GPT ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# --- Historique des lots vus ---
SEEN_FILE = "seen.json"
if os.path.exists(SEEN_FILE):
    with open(SEEN_FILE, "r") as f:
        seen_lots = set(json.load(f))
else:
    seen_lots = set()

# --- Flask pour UptimeRobot ---
app = Flask(__name__)
@app.route("/")
def home():
    return "✅ Bot Catawiki Requests + GPT actif !"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

# --- Parsing des valeurs en euro ---
def parse_euro(value_str):
    if not value_str:
        return None
    clean = re.sub(r"[^\d]", "", value_str)
    try:
        return int(clean)
    except:
        return None

# --- GPT : détecter tous les sélecteurs ---
def get_selectors_with_gpt(html_snippet):
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
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role":"user","content":prompt}],
            temperature=0
        )
        selectors_json = response['choices'][0]['message']['content']
        try:
            selectors = json.loads(selectors_json)
        except json.JSONDecodeError:
            print("❌ Erreur JSON GPT invalide :", selectors_json)
            return None
        return selectors
    except Exception as e:
        print("❌ Erreur GPT :", e)
        return None

# --- Extraire détails d'un lot ---
def get_lot_details(lot_url):
    try:
        print(f"\n🔎 URL Lot : {lot_url}")
        r = requests.get(lot_url)
        html_snippet = r.text
        print("\nDEBUG HTML du lot (3000 chars max) :", html_snippet[:3000], "...\n")

        selectors = get_selectors_with_gpt(html_snippet)
        if not selectors:
            print("⚠️ GPT n'a trouvé aucun sélecteur pour ce lot !")
            return None

        print("DEBUG JSON GPT :", json.dumps(selectors, indent=2))

        soup = BeautifulSoup(html_snippet, "html.parser")

        def extract_first(tag):
            if isinstance(tag, list):
                for t in tag:
                    element = soup.select_one(t)
                    if element:
                        return element.get_text(strip=True)
                return None
            elif isinstance(tag, str):
                element = soup.select_one(tag)
                return element.get_text(strip=True) if element else None
            return None

        title = extract_first(selectors.get("title", [])) or "N/A"
        price_str = extract_first(selectors.get("price", []))
        price = parse_euro(price_str)
        est_str = extract_first(selectors.get("estimation", []))
        estimation = parse_euro(est_str)
        time_str = extract_first(selectors.get("remaining", []))
        remaining = None
        if time_str:
            m = re.search(r"(?:(\d+)d)?\s*(?:(\d+)h)?\s*(\d+)m", time_str)
            if m:
                days = int(m.group(1)) if m.group(1) else 0
                hours = int(m.group(2)) if m.group(2) else 0
                minutes = int(m.group(3))
                remaining = timedelta(days=days, hours=hours, minutes=minutes)

        print(f"DEBUG LOT FINAL: {title} | Prix: {price} | Estimation: {estimation} | Temps restant: {remaining}")
        return {"title": title, "url": lot_url, "price": price, "estimation": estimation, "remaining": remaining}

    except Exception as e:
        print(f"❌ Erreur récupération lot {lot_url} :", e)
        return None

# --- Scraper tous les lots ---
def scrape_catawiki():
    print("\n🔍 Scraping Catawiki avec Requests + GPT (Super Verbose)...")
    base_url = "https://www.catawiki.com/en/c/333-watches"
    r = requests.get(base_url)
    soup = BeautifulSoup(r.text, "html.parser")

    items = soup.select("a.LotTile-link")
    print("DEBUG: Nombre de lots trouvés :", len(items))

    for item in items:
        lot_url = item.get("href")
        if lot_url.startswith("/"):
            lot_url = "https://www.catawiki.com" + lot_url
        if lot_url in seen_lots:
            continue
        seen_lots.add(lot_url)
        get_lot_details(lot_url)
        time.sleep(1)

    # Sauvegarde des lots vus
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen_lots), f)

# --- Lancer Flask ---
threading.Thread(target=run_flask).start()
print("🚀 Bot Requests + GPT lancé. Vérification immédiate...")

# --- Exécution immédiate ---
scrape_catawiki()

# --- Scheduler toutes les heures ---
schedule.every().hour.do(scrape_catawiki)

while True:
    schedule.run_pending()
    time.sleep(60)
