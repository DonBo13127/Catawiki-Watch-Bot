import os
import time
import smtplib
from email.mime.text import MIMEText
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from apscheduler.schedulers.background import BackgroundScheduler
import openai
import json

# --- Configuration ---
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_PASSWORD = os.environ.get("GMAIL_PASSWORD")
TARGET_URL = "https://www.catawiki.com/en/c/333-watches"

openai.api_key = OPENAI_API_KEY

# --- Email function ---
def send_email(subject, body):
    msg = MIMEText(body, "html")
    msg['Subject'] = subject
    msg['From'] = GMAIL_USER
    msg['To'] = GMAIL_USER
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.sendmail(GMAIL_USER, GMAIL_USER, msg.as_string())
        server.quit()
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ✅ Email envoyé")
    except Exception as e:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ❌ Erreur email : {e}")

# --- GPT Selectors function ---
def get_selectors_with_gpt(html_sample):
    prompt = f"""
Tu es un expert en scraping HTML. Voici un extrait de page HTML : {html_sample[:2000]}
Fournis-moi les sélecteurs CSS pour extraire chaque lot de montre :
- Titre de la montre
- Prix actuel
- Estimation
- Temps restant de l'enchère
Retourne uniquement du JSON avec les clés title, price, estimation, remaining.
"""
    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        content = response.choices[0].message.content
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] DEBUG Sélecteurs GPT : {content}")
        return json.loads(content)
    except Exception as e:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ❌ Erreur GPT : {e}")
        return {"title": [], "price": [], "estimation": [], "remaining": []}

# --- Scraping function ---
def scrape_catawiki():
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 🔍 Scraping Catawiki (Playwright + GPT)...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(TARGET_URL)
            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            # GPT pour trouver les sélecteurs
            selectors = get_selectors_with_gpt(html)

            # Extraire les lots
            lots = soup.select(selectors.get("title", ["div"]))  # fallback
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] DEBUG Nombre de lots trouvés : {len(lots)}")

            interesting = []
            for lot in lots:
                try:
                    title = lot.get_text(strip=True)
                    # Exemple : récupérer les autres infos via soup.select_one(sel)
                    # price = ...
                    # estimation = ...
                    # remaining = ...
                    # filtrage logique ici
                    interesting.append(title)
                    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Lot trouvé : {title[:50]}")
                except Exception as e:
                    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ❌ Erreur lot : {e}")

            if interesting:
                body = "<br>".join(interesting)
                send_email("Lots Catawiki intéressants", body)
            else:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ⏳ Aucun lot intéressant trouvé cette vérification.")
            browser.close()
    except Exception as e:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ❌ Erreur HTTP/Playwright : {e}")

# --- Scheduler ---
scheduler = BackgroundScheduler()
scheduler.add_job(scrape_catawiki, 'interval', hours=1)
scheduler.start()

# --- Lancement immédiat ---
scrape_catawiki()

# --- Flask simple pour Railway ---
from flask import Flask
app = Flask(__name__)

@app.route("/")
def index():
    return "Bot Catawiki + GPT actif."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
