"""
Financero - Envoi de l'email quotidien d'alertes
----------------------------------------------------
Regroupe les alertes pas encore envoyees, par entreprise, et envoie
un email recapitulatif a chacune (si elle a une adresse renseignee).
Marque ensuite ces alertes comme envoyees pour ne jamais les renvoyer.

Utilisation :
    python3 envoyer_alertes.py
"""

import os
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timezone
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
url = os.environ["SUPABASE_URL"]
cle = os.environ["SUPABASE_SERVICE_KEY"]
client = create_client(url, cle)

GMAIL_ADRESSE = os.environ["GMAIL_ADRESSE"]
GMAIL_MOT_DE_PASSE = os.environ["GMAIL_MOT_DE_PASSE"]


def envoyer_email(destinataire, sujet, corps):
    message = MIMEText(corps)
    message["Subject"] = sujet
    message["From"] = GMAIL_ADRESSE
    message["To"] = destinataire

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as serveur:
        serveur.login(GMAIL_ADRESSE, GMAIL_MOT_DE_PASSE)
        serveur.sendmail(GMAIL_ADRESSE, destinataire, message.as_string())


entreprises = client.table("entreprises").select("id, nom, email").execute().data

for entreprise in entreprises:
    entreprise_id = entreprise["id"]
    nom = entreprise["nom"]
    email = entreprise.get("email")

    if not email:
        print(f"{nom} : pas d'adresse email renseignee, ignore.")
        continue

    alertes = (
        client.table("alertes")
        .select("*")
        .eq("entreprise_id", entreprise_id)
        .is_("envoyee_le", "null")
        .execute()
        .data
    )

    if not alertes:
        print(f"{nom} : aucune nouvelle alerte, pas d'email envoye.")
        continue

    corps = "Voici les nouvelles alertes detectees sur vos finances :\n\n"
    for alerte in alertes:
        corps += f"- {alerte['texte']}\n"
    corps += "\n---\nFinancero"

    envoyer_email(email, f"Financero - {len(alertes)} nouvelle(s) alerte(s)", corps)

    maintenant = datetime.now(timezone.utc).isoformat()
    for alerte in alertes:
        client.table("alertes").update({"envoyee_le": maintenant}).eq("id", alerte["id"]).execute()

    print(f"{nom} : email envoye a {email} avec {len(alertes)} alerte(s).")

print("\nTermine.")
