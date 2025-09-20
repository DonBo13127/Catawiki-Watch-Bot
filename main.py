import os
import time
import smtplib
import traceback
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from bs4 import BeautifulSoup
import openai
from datetime import datetime, timedelta

# =============================
# Configuration
# =============================
URL_CATAWIKI = "https://www.catawiki.com/en/c/333-watches"
MAX_PRICE = 2500
MIN_ESTIMATION = 5000
MAX_REMAINING_HOURS = 24
CHECK_INTERVAL_HOURS = 1  # Scheduler toutes les heures

# Variables d'environnement
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_TO = os.getenv("EMAIL_TO", EMAIL_ADDRESS)

# =============================
# Initialisation OpenAI
# =============================
if not OPENAI_API_KEY:
    raise ValueError("❌ La variable d'environnement OPENAI_API_KEY n'est pas définie !")

openai.api_key = OPENAI_API_KEY

# =============================
# Fonctions utilitaires
# =============================
def send_email(subject, body):
    """Envoi d'un email simple avec HTML"""
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = EMAIL_TO
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html"))

        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, EMAIL_TO, msg.as_string())
        server.quit()
        print(f"[{datetime.now()}] ✅ Email envoyé à {EMAIL_TO}")
    except Exception:
        print(f"[{datetime.now()}] ❌ Erreur envoi email :\n{traceback.format_exc()}")

def get_gpt_selectors(html_sample):
    """Demande à GPT de trouver les sélecteurs pour titre, prix, estimation et temps restant"""
    try:
        prompt = f"""
        Tu es un assistant expert en scraping.
        Voici un extrait HTML d'une page Catawiki : 
        {html_sample}

        Fournis uniquement un JSON avec les sélecteurs CSS :
        {{
            "title": [],
            "price": [],
            "estimation": [],
            "remaining": []
        }}
        Les sélecteurs doivent être précis pour chaque lot de montre.
        """
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        selectors_json = response.choices[0].message.content
        print(f"[{datetime.now()}] DEBUG Sélecteurs GPT : {selectors_json}")
        return selectors_json
    except Exception:
        print(f"[{datetime.now()}] ❌ Erreur GPT :\n{traceback.format_exc()}")
        return None

def parse_price(text):
    """Convertit le texte du prix en float"""
    try:
        return float("".join(c for c in text if c.isdigit() or c=='.'))
    except:
        return 0

def parse_remaining(text):
    """Convertit le texte restant en heures"""
    try:
        if "h" in text:
            return int(text.replace("h","").strip())
        elif "d" in text:
            return int(text.replace("d","").strip())*24
    except:
        return 9999

# =============================
# Fonction principale
# =============================
def scrape_catawiki():
    print(f"[{datetime.now()}] 🚀 Scraping Catawiki + GPT lancé...")
    try:
        # 1) Récupérer la page principale
        response = requests.get(URL_CATAWIKI, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code != 200:
            print(f"[{datetime.now()}] ❌ Erreur HTTP : {response.status_code}")
            return
        soup = BeautifulSoup(response.text, "html.parser")
        print(f"[{datetime.now()}] DEBUG page principale récupérée")

        # 2) Exemple HTML d'un lot pour GPT
        example_lot = str(soup.find("div", {"class": "ListingGridstyles__Card"}))
        selectors = get_gpt_selectors(example_lot)
        if not selectors:
            print(f"[{datetime.now()}] ⚠️ GPT n'a trouvé aucun sélecteur !")
            return

        # 3) Scraper tous les lots
        lots = soup.select(".ListingGridstyles__Card")
        print(f"[{datetime.now()}] DEBUG Nombre de lots trouvés : {len(lots)}")

        interesting_lots = []

        for lot in lots:
            try:
                title = lot.select_one(".ListingCardstyles__Title") 
                title_text = title.get_text(strip=True) if title else "N/A"

                price = lot.select_one(".ListingCardstyles__CurrentBid")
                price_value = parse_price(price.get_text()) if price else 0

                estimation = lot.select_one(".ListingCardstyles__Estimation")
                est_value = parse_price(estimation.get_text()) if estimation else 0

                remaining = lot.select_one(".ListingCardstyles__RemainingTime")
                remaining_hours = parse_remaining(remaining.get_text()) if remaining else 9999

                print(f"[{datetime.now()}] DEBUG Lot: {title_text} | Price: {price_value} | Est: {est_value} | Remaining: {remaining_hours}h")

                if price_value <= MAX_PRICE and est_value >= MIN_ESTIMATION and remaining_hours <= MAX_REMAINING_HOURS:
                    interesting_lots.append({
                        "title": title_text,
                        "price": price_value,
                        "estimation": est_value,
                        "remaining_hours": remaining_hours,
                        "url": lot.find("a")["href"] if lot.find("a") else URL_CATAWIKI
                    })
            except Exception:
                print(f"[{datetime.now()}] ❌ Erreur parsing lot :\n{traceback.format_exc()}")

        # 4) Envoi email si au moins 1 lot
        if interesting_lots:
            html_content = "<h2>Lots intéressants trouvés :</h2>"
            for l in interesting_lots:
                html_content += f"<p><b>{l['title']}</b><br>Prix : {l['price']}€ | Estimation : {l['estimation']}€ | Temps restant : {l['remaining_hours']}h<br><a href='{l['url']}'>Lien</a></p>"
            send_email("🚨 Lots intéressants Catawiki", html_content)
        else:
            print(f"[{datetime.now()}] ⏳ Aucun lot intéressant trouvé cette vérification.")

    except Exception:
        print(f"[{datetime.now()}] ❌ Erreur générale :\n{traceback.format_exc()}")

# =============================
# Scheduler simple
# =============================
if __name__ == "__main__":
    while True:
        scrape_catawiki()
        print(f"[{datetime.now()}] ⏰ Scheduler activé : prochaine vérification dans {CHECK_INTERVAL_HOURS} heures...")
        time.sleep(CHECK_INTERVAL_HOURS * 3600)
