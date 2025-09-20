import os
import requests
from bs4 import BeautifulSoup
import openai
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from threading import Thread

# --- CONFIG ---
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASS = os.getenv("GMAIL_PASS")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "gpt-4"  # ou gpt-3.5-turbo

openai.api_key = OPENAI_API_KEY

URL_CATAWIKI = "https://www.catawiki.com/en/c/333-watches"
CHECK_INTERVAL = 60*60  # 1h

# --- EMAIL ---
def send_email(subject, content):
    try:
        msg = MIMEMultipart()
        msg['From'] = GMAIL_USER
        msg['To'] = GMAIL_USER
        msg['Subject'] = subject
        msg.attach(MIMEText(content, 'plain'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_PASS)
        server.sendmail(GMAIL_USER, GMAIL_USER, msg.as_string())
        server.quit()
        print("✅ Email envoyé")
    except Exception as e:
        print("❌ Erreur email :", e)

# --- GPT SELECTORS ---
def analyze_selectors_with_gpt(html):
    prompt = f"""
Tu es un expert en web scraping. Analyse le HTML suivant et renvoie un JSON
avec les bons sélecteurs CSS pour chaque champ:
- title
- price
- estimation
- remaining (temps restant)
Renvoie le JSON seulement, sans explication.
HTML : {html[:5000]}
"""
    try:
        response = openai.ChatCompletion.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        result = response['choices'][0]['message']['content']
        return result
    except Exception as e:
        print("❌ Erreur GPT :", e)
        return {}

# --- SCRAPING ---
def scrape_catawiki():
    print("🚀 Scraping Catawiki + GPT (optimisé) ...")
    try:
        resp = requests.get(URL_CATAWIKI)
        if resp.status_code != 200:
            print("❌ Erreur HTTP :", resp.status_code)
            return
        soup = BeautifulSoup(resp.text, "html.parser")
        lots = soup.select("article")
        print(f"DEBUG: {len(lots)} lots détectés sur la page")

        for idx, lot in enumerate(lots, start=1):
            html_lot = str(lot)[:1000]
            print(f"\n--- Lot {idx} ---")
            print("URL du lot:", lot.select_one("a")["href"] if lot.select_one("a") else "N/A")
            print("HTML limité:", html_lot)

            # GPT uniquement pour lots potentiellement intéressants
            selectors_json = analyze_selectors_with_gpt(html_lot)
            print("JSON GPT pour ce lot :", selectors_json)

            # TODO: appliquer filtrage réel
            # Exemple :
            # prix = ...
            # estimation = ...
            # remaining = ...
            # if prix < 2500 and estimation > 5000 and remaining < 24h:
            #     send_email(f"Lot intéressant: {title}", f"URL: {url}")

    except Exception as e:
        print("❌ Erreur scraping:", e)

# --- SCHEDULER ---
def scheduler():
    while True:
        scrape_catawiki()
        print(f"⏰ Scheduler activé : prochaine vérification dans {CHECK_INTERVAL/3600} heures...")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    print("🚀 Bot Catawiki + GPT optimisé lancé. Vérification immédiate...")
    Thread(target=scheduler).start()
