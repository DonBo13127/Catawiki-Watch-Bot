import os
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.sync_api import sync_playwright
import openai
from bs4 import BeautifulSoup
import threading

# --- CONFIG ---
GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_PASS = os.environ.get("GMAIL_PASS")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
CHECK_INTERVAL = 3600  # 1h en secondes
CATAWIKI_URL = "https://www.catawiki.com/en/c/333-watches"

openai.api_key = OPENAI_API_KEY

# --- FONCTIONS MAIL ---
def send_email(subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = GMAIL_USER
        msg['To'] = GMAIL_USER
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_PASS)
        server.send_message(msg)
        server.quit()
        print(f"📧 Email envoyé : {subject}")
    except Exception as e:
        print(f"❌ Erreur envoi mail : {e}")

# --- FONCTION GPT POUR IDENTIFIER LES SELECTEURS ---
def gpt_find_selectors(html_snippet):
    try:
        prompt = f"""
Tu es un expert en scraping HTML. Analyse le code HTML ci-dessous et renvoie les selecteurs CSS exacts pour récupérer :
1. le titre de la montre
2. le prix actuel
3. l'estimation
4. le temps restant de l'enchère

Retourne sous format JSON comme ceci :
{{"title": "SELECTOR", "price": "SELECTOR", "estimation": "SELECTOR", "remaining": "SELECTOR"}}

HTML à analyser :
{html_snippet[:2000]}  # limite à 2000 caractères pour GPT
"""
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        content = response.choices[0].message['content']
        import json
        selectors = json.loads(content)
        return selectors
    except Exception as e:
        print(f"❌ Erreur GPT : {e}")
        return {"title": None, "price": None, "estimation": None, "remaining": None}

# --- FONCTION SCRAPING ---
def scrape_catawiki():
    print("🔍 Scraping Catawiki (Playwright + GPT)...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(CATAWIKI_URL, timeout=60000)
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')

            lots = soup.select("a[href*='/en/l/']")  # tous les liens de lots
            lots_urls = list(dict.fromkeys([lot['href'] for lot in lots if lot.get('href')]))  # unique + pas None
            print(f"DEBUG: {len(lots_urls)} lots détectés")

            interesting_lots = []

            for url in lots_urls:
                full_url = f"https://www.catawiki.com{url}" if url.startswith("/") else url
                page.goto(full_url, timeout=60000)
                lot_html = page.content()
                selectors = gpt_find_selectors(lot_html)

                print(f"DEBUG URL: {full_url}")
                print(f"DEBUG SELECTORS: {selectors}")

                # Vérification que GPT a trouvé quelque chose
                if not selectors or None in selectors.values():
                    print("⚠️ GPT n'a pas trouvé tous les selecteurs pour ce lot")
                    continue

                lot_soup = BeautifulSoup(lot_html, 'html.parser')

                def safe_get(soup, sel):
                    try:
                        el = soup.select_one(sel)
                        return el.get_text(strip=True) if el else None
                    except:
                        return None

                title = safe_get(lot_soup, selectors['title'])
                price_text = safe_get(lot_soup, selectors['price'])
                estimation_text = safe_get(lot_soup, selectors['estimation'])
                remaining_text = safe_get(lot_soup, selectors['remaining'])

                if not price_text or not remaining_text:
                    continue

                # Convertir prix et estimation en float
                try:
                    price = float(''.join(filter(str.isdigit, price_text)))
                    estimation = float(''.join(filter(str.isdigit, estimation_text)))
                except:
                    price = 0
                    estimation = 0

                # Convertir remaining_text en heures (ex: "23h 15m")
                try:
                    h, m = 0, 0
                    if 'h' in remaining_text:
                        h = int(remaining_text.split('h')[0])
                        if 'm' in remaining_text:
                            m = int(remaining_text.split('h')[1].split('m')[0])
                    remaining_hours = h + m/60
                except:
                    remaining_hours = 999

                # Filtre : estimation > 5000, prix < 2500, remaining < 24h
                if estimation > 5000 and price < 2500 and remaining_hours <= 24:
                    interesting_lots.append(f"{title} | {price_text} | {estimation_text} | {remaining_text} | {full_url}")

            if interesting_lots:
                body = "\n".join(interesting_lots)
                send_email("Lots intéressants Catawiki", body)
            else:
                print("⏳ Aucun lot intéressant trouvé cette vérification.")

            browser.close()
    except Exception as e:
        print(f"❌ Erreur HTTP/Playwright : {e}")

# --- SCHEDULER ---
def scheduler():
    scrape_catawiki()
    threading.Timer(CHECK_INTERVAL, scheduler).start()
    print(f"⏰ Scheduler activé : scraping toutes les {CHECK_INTERVAL/3600} heures...")

# --- MAIN ---
if __name__ == "__main__":
    print("🚀 Bot Catawiki + GPT optimisé et super verbose lancé. Vérification immédiate...")
    scheduler()
