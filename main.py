import requests
from bs4 import BeautifulSoup
import json
import re
import smtplib
import time
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from openai import OpenAI
import os

# === CONFIGURATION ===
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
TO_EMAIL = os.environ.get("TO_EMAIL")

CATAWIKI_URL = "https://www.catawiki.com/en/c/333-watches"

# Scheduler interval (en secondes)
INTERVAL = 3600  # toutes les heures

# === INITIALISATION GPT ===
client = OpenAI(api_key=OPENAI_API_KEY)

def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

# === FONCTION GPT POUR TROUVER LES SELECTEURS ===
def gpt_find_selectors(html):
    try:
        prompt = f"""
Vous êtes un assistant expert en scraping. Vous analysez le HTML suivant et fournissez uniquement un JSON avec les bons sélecteurs CSS pour extraire :
- le titre du lot
- le prix actuel
- l'estimation
- le temps restant (format texte comme '23h 15m')

HTML :
{html}

Répondez uniquement avec un JSON :
{{"title": "...", "price": "...", "estimation": "...", "remaining": "..."}}
"""
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        content = response.choices[0].message.content.strip()
        return json.loads(content)
    except Exception as e:
        log(f"❌ Erreur GPT : {e}")
        return {"title": [], "price": [], "estimation": [], "remaining": []}

# === FONCTION POUR EXTRAIRE TEXTE AVEC SELECTEUR ===
def extract_with_selector(soup, selector):
    if isinstance(selector, list):
        for sel in selector:
            el = soup.select_one(sel)
            if el: return el.get_text(strip=True)
    else:
        el = soup.select_one(selector)
        if el: return el.get_text(strip=True)
    return None

# === FONCTION PRINCIPALE ===
def scrape_catawiki():
    log("🔍 Scraping Catawiki (Playwright + GPT)...")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        resp = requests.get(CATAWIKI_URL, headers=headers)
        if resp.status_code != 200:
            log(f"❌ Erreur HTTP : {resp.status_code}")
            return

        soup = BeautifulSoup(resp.text, "html.parser")
        # Sélecteur générique pour les cartes de lots
        lots = soup.find_all("a", class_=re.compile("Card.*"))
        log(f"DEBUG: {len(lots)} lots détectés")

        for lot in lots:
            lot_url = lot.get("href")
            if not lot_url.startswith("http"):
                lot_url = "https://www.catawiki.com" + lot_url
            log(f"DEBUG: Analyse lot {lot_url}")

            # HTML complet pour GPT
            lot_html = str(lot)
            selectors = gpt_find_selectors(lot_html)
            log(f"DEBUG Sélecteurs GPT : {selectors}")

            # Extraction des données
            lot_soup = BeautifulSoup(lot_html, "html.parser")
            title = extract_with_selector(lot_soup, selectors["title"])
            price = extract_with_selector(lot_soup, selectors["price"])
            estimation = extract_with_selector(lot_soup, selectors["estimation"])
            remaining = extract_with_selector(lot_soup, selectors["remaining"])
            log(f"DEBUG: Titre: {title}, Prix: {price}, Estimation: {estimation}, Remaining: {remaining}")

            # Filtrage simple
            try:
                price_val = float(re.sub(r"[^\d.]", "", price))
                est_val = float(re.sub(r"[^\d.]", "", estimation))
                hours_remaining = 24  # par défaut
                if remaining:
                    h_match = re.search(r"(\d+)h", remaining)
                    if h_match: hours_remaining = int(h_match.group(1))
            except Exception as e:
                log(f"⚠️ Erreur conversion valeurs : {e}")
                continue

            if price_val <= 2500 and est_val >= 5000 and hours_remaining <= 24:
                send_email(title, lot_url, price, estimation, remaining)

        log("⏳ Vérification terminée.")

    except Exception as e:
        log(f"❌ Erreur générale : {e}")

# === FONCTION ENVOI EMAIL ===
def send_email(title, url, price, estimation, remaining):
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_USER
        msg["To"] = TO_EMAIL
        msg["Subject"] = f"Nouvelle enchère intéressante : {title}"

        body = f"""
Titre: {title}
Prix: {price}
Estimation: {estimation}
Temps restant: {remaining}
Lien: {url}
"""
        msg.attach(MIMEText(body, "plain"))
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        log(f"📧 Email envoyé pour le lot : {title}")
    except Exception as e:
        log(f"❌ Erreur envoi email : {e}")

# === SCHEDULER ===
def scheduler():
    while True:
        scrape_catawiki()
        log(f"⏰ Prochaine vérification dans {INTERVAL/3600} heures...")
        time.sleep(INTERVAL)

# === LANCEMENT ===
if __name__ == "__main__":
    log("🚀 Bot Catawiki + GPT optimisé et super verbose lancé. Vérification immédiate...")
    threading.Thread(target=scheduler, daemon=True).start()

    # Flask minimal pour garder le service actif sur Render / Railway
    from flask import Flask
    app = Flask(__name__)

    @app.route("/")
    def home():
        return "Bot Catawiki + GPT actif !"

    app.run(host="0.0.0.0", port=8080)
