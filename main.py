import os
import time
import smtplib
import json
import requests
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import openai
import schedule

# --- CONFIGURATION ---
GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_PASS = os.environ.get("GMAIL_PASS")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
CATALOG_URL = "https://www.catawiki.com/en/c/333-watches"
MIN_ESTIMATION = 5000
MAX_PRICE = 2500
MAX_REMAINING_HOURS = 24

openai.api_key = OPENAI_API_KEY

# --- LOGGING UTILE ---
def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

# --- ENVOI MAIL ---
def send_email(lots):
    if not lots:
        log("ℹ️ Aucun lot intéressant à envoyer par mail.")
        return
    try:
        msg = MIMEMultipart()
        msg['From'] = GMAIL_USER
        msg['To'] = GMAIL_USER
        msg['Subject'] = f"Catawiki Watch Alert - {len(lots)} lots"
        body = "\n\n".join([f"{lot['title']} - {lot['price']} - {lot['remaining']}h left\n{lot['url']}" for lot in lots])
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_PASS)
        server.send_message(msg)
        server.quit()
        log(f"✅ Email envoyé avec {len(lots)} lots.")
    except Exception as e:
        log(f"❌ Erreur lors de l'envoi du mail : {e}")

# --- GPT POUR TROUVER LES SELECTEURS ---
def get_selectors_from_gpt(html_sample):
    prompt = f"""
Analyse ce HTML et renvoie les selecteurs CSS pour récupérer:
- Le titre du lot
- Le prix actuel
- L'estimation
- Le temps restant en heures

Répond uniquement en JSON avec les clés: title, price, estimation, remaining.
HTML:
{html_sample[:3000]} 
"""
    try:
        resp = openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        content = resp.choices[0].message['content']
        selectors = json.loads(content)
        log(f"DEBUG Sélecteurs GPT : {selectors}")
        return selectors
    except Exception as e:
        log(f"❌ Erreur GPT : {e}")
        return {"title": [], "price": [], "estimation": [], "remaining": []}

# --- SCRAPING ---
def scrape_catawiki():
    log("🔍 Scraping Catawiki (optimisé + logs détaillés)...")
    try:
        resp = requests.get(CATALOG_URL)
        if resp.status_code != 200:
            log(f"❌ Erreur HTTP : {resp.status_code}")
            return
        soup = BeautifulSoup(resp.text, 'html.parser')
        lot_elements = soup.select("a[href*='/lot/']")  # Tous les lots
        log(f"DEBUG Nombre de lots détectés sur la page : {len(lot_elements)}")

        # Prendre un échantillon pour GPT
        sample_html = str(lot_elements[0]) if lot_elements else ""
        selectors = get_selectors_from_gpt(sample_html)

        lots_to_send = []

        for lot in lot_elements:
            url = "https://www.catawiki.com" + lot['href']
            log(f"DEBUG Analyse lot : {url}")

            lot_html = requests.get(url).text
            lot_soup = BeautifulSoup(lot_html, 'html.parser')

            # Extraire infos avec sélecteurs GPT
            try:
                title = lot_soup.select_one(selectors.get("title", [""])[0]).get_text(strip=True) if selectors.get("title") else "N/A"
                price_str = lot_soup.select_one(selectors.get("price", [""])[0]).get_text(strip=True) if selectors.get("price") else "0"
                estimation_str = lot_soup.select_one(selectors.get("estimation", [""])[0]).get_text(strip=True) if selectors.get("estimation") else "0"
                remaining_str = lot_soup.select_one(selectors.get("remaining", [""])[0]).get_text(strip=True) if selectors.get("remaining") else "0"

                price = float("".join(filter(str.isdigit, price_str)))
                estimation = float("".join(filter(str.isdigit, estimation_str)))
                remaining_hours = float("".join(filter(str.isdigit, remaining_str.split()[0])))

                log(f"DEBUG Lot : {title} | Price: {price} | Estimation: {estimation} | Remaining: {remaining_hours}h")

                if price <= MAX_PRICE and estimation >= MIN_ESTIMATION and remaining_hours <= MAX_REMAINING_HOURS:
                    lots_to_send.append({
                        "title": title,
                        "price": price,
                        "estimation": estimation,
                        "remaining": remaining_hours,
                        "url": url
                    })
            except Exception as e:
                log(f"❌ Erreur parsing lot {url} : {e}")

        send_email(lots_to_send)

    except Exception as e:
        log(f"❌ Erreur scraping général : {e}")

# --- SCHEDULER ---
def run_scheduler():
    scrape_catawiki()  # exécution immédiate
    schedule.every(1).hours.do(scrape_catawiki)
    log("⏰ Scheduler activé : scraping toutes les heures...")
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    log("🚀 Bot Catawiki + GPT optimisé et super verbose lancé. Vérification immédiate...")
    run_scheduler()
