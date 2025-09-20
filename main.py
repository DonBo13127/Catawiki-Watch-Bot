import os
import requests
from bs4 import BeautifulSoup
from flask import Flask
import schedule
import time
import threading
import openai
import smtplib
from email.mime.text import MIMEText

# --- CONFIGURATION ---
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
TARGET_URL = "https://www.catawiki.com/en/c/333-watches"

openai.api_key = OPENAI_API_KEY

# --- FLASK ---
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot Catawiki + GPT en fonctionnement 🚀"

# --- FONCTIONS BOT ---
def analyse_selectors(html):
    try:
        prompt = f"""
Analyse ce HTML et retourne les selecteurs CSS pour:
- titre de la montre
- prix actuel
- estimation
- temps restant de l'enchère
HTML : {html[:2000]}  # limite pour éviter trop long
Réponds en JSON avec les clés : title, price, estimation, remaining
"""
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        selectors = response.choices[0].message.content
        print(f"DEBUG Sélecteurs GPT : {selectors}")
        return selectors
    except Exception as e:
        print(f"❌ Erreur GPT : {e}")
        return {}

def scrape_catawiki():
    print("🚀 Vérification des enchères Catawiki...")
    try:
        resp = requests.get(TARGET_URL, headers={"User-Agent":"Mozilla/5.0"})
        if resp.status_code != 200:
            print(f"❌ Erreur HTTP : {resp.status_code}")
            return

        html = resp.text
        selectors = analyse_selectors(html)

        soup = BeautifulSoup(html, "html.parser")
        # Ici tu peux parser avec les selecteurs GPT (ex: soup.select(selectors['title']))
        print("DEBUG: page analysée")

        # Exemple de condition
        print("⏳ Aucune enchère intéressante trouvée cette vérification.")

    except Exception as e:
        print(f"❌ Erreur scraping : {e}")

def send_email(subject, body):
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = EMAIL_ADDRESS
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, EMAIL_ADDRESS, msg.as_string())
        server.quit()
        print("📧 Email envoyé !")
    except Exception as e:
        print(f"❌ Erreur email : {e}")

def run_scheduler():
    scrape_catawiki()
    schedule.every(1).hours.do(scrape_catawiki)
    while True:
        schedule.run_pending()
        time.sleep(60)

# --- THREAD FLASK + SCHEDULER ---
if __name__ == "__main__":
    threading.Thread(target=run_scheduler, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)
