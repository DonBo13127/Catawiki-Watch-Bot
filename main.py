import os
html_parts.append("</ul></body></html>")


text_body = "\n\n".join(text_parts)
html_body = '\n'.join(html_parts)


part1 = MIMEText(text_body, 'plain')
part2 = MIMEText(html_body, 'html')


msg.attach(part1)
msg.attach(part2)


# Envoyer via SMTP
try:
server = smtplib.SMTP('smtp.gmail.com', 587)
server.ehlo()
server.starttls()
server.login(gmail_user, gmail_pw)
server.sendmail(gmail_user, recipient, msg.as_string())
server.quit()
logger.info("Email envoyé à %s", recipient)
return True
except Exception as e:
logger.exception("Erreur envoi email: %s", e)
return False




# --- Main job ---


def job():
logger.info("Démarrage du scan Catawiki...")
session = requests.Session()
session.headers.update(HEADERS)


seen = load_seen()
new_seen = set(seen)


try:
candidates = find_candidate_auctions(session, pages_to_scan=5)
except Exception as e:
logger.exception("Erreur lors de la recherche de candidates: %s", e)
return


results_to_send = []


for url in candidates:
if url in seen:
continue
details = extract_auction_details(session, url)
if not details:
continue
if is_worthy(details):
results_to_send.append(details)
new_seen.add(url)
else:
# On peut marquer quand même comme vu pour éviter retraits fréquents
new_seen.add(url)
time.sleep(0.7)


# Sauvegarder seen
save_seen(new_seen)


if results_to_send:
send_email(results_to_send)
else:
logger.info("Aucun résultat conforme trouvé.")




if __name__ == '__main__':
# Lancer la première exécution immédiatement
job()


# Planifier exécution toutes les heures
schedule.every(1).hours.do(job)


logger.info("Scheduler démarré. Monitoring toutes les heures.")
while True:
schedule.run_pending()
time.sleep(5)
