"""
Financero - Detection d'anomalies (version Supabase)
--------------------------------------------------------
Lit les factures directement depuis Supabase, detecte les hausses
anormales et les doublons (meme logique validee sur les 3 pilotes),
et enregistre chaque alerte dans la table `alertes` - sans jamais
dupliquer une alerte deja enregistree.

Utilisation :
    python3 detecter_anomalies_supabase.py
"""

import os
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
url = os.environ["SUPABASE_URL"]
cle = os.environ["SUPABASE_SERVICE_KEY"]
client = create_client(url, cle)

SEUIL_PLANCHER = 0.20


def deja_enregistree(entreprise_id, type_alerte, fournisseur, date_detection):
    resultat = (
        client.table("alertes")
        .select("id")
        .eq("entreprise_id", entreprise_id)
        .eq("type", type_alerte)
        .eq("fournisseur", fournisseur)
        .eq("date_detection", date_detection)
        .execute()
    )
    return len(resultat.data) > 0


def enregistrer_alerte(entreprise_id, type_alerte, fournisseur, date_detection, montant, variation_pct, texte):
    if deja_enregistree(entreprise_id, type_alerte, fournisseur, date_detection):
        return False
    client.table("alertes").insert({
        "entreprise_id": entreprise_id,
        "type": type_alerte,
        "fournisseur": fournisseur,
        "date_detection": date_detection,
        "montant": montant,
        "variation_pct": variation_pct,
        "texte": texte,
    }).execute()
    return True


entreprises = client.table("entreprises").select("id, nom").execute().data

for entreprise in entreprises:
    entreprise_id = entreprise["id"]
    nom = entreprise["nom"]

    factures_brutes = (
        client.table("factures_fournisseurs")
        .select("*")
        .eq("entreprise_id", entreprise_id)
        .execute()
        .data
    )
    if not factures_brutes:
        print(f"{nom} : aucune facture en base, ignore.")
        continue

    factures = pd.DataFrame(factures_brutes)
    factures["date_facture"] = pd.to_datetime(factures["date_facture"])
    factures = factures.sort_values(["fournisseur", "date_facture"])

    nb_nouvelles = 0

    # --- Hausses anormales (seuil adaptatif selon la volatilite habituelle) ---
    for fournisseur, groupe in factures.groupby("fournisseur"):
        groupe = groupe.sort_values("date_facture")
        montants_precedents = []
        for _, ligne in groupe.iterrows():
            montant = float(ligne["montant_ht"])
            if len(montants_precedents) >= 1:
                moyenne = sum(montants_precedents) / len(montants_precedents)
                if len(montants_precedents) >= 3:
                    volatilite = pd.Series(montants_precedents).std() / moyenne
                    seuil = max(SEUIL_PLANCHER, 2 * volatilite)
                else:
                    seuil = SEUIL_PLANCHER
                variation = (montant - moyenne) / moyenne
                if variation >= seuil:
                    date_str = ligne["date_facture"].strftime("%Y-%m-%d")
                    texte = (
                        f"Le {ligne['date_facture'].strftime('%d/%m/%Y')}, {fournisseur} a facture "
                        f"{montant:.2f} EUR HT (facture {ligne['numero_facture']}), soit "
                        f"{variation*100:.1f}% de plus que sa moyenne habituelle ({moyenne:.2f} EUR)."
                    )
                    if enregistrer_alerte(entreprise_id, "hausse_prix", fournisseur, date_str,
                                           montant, round(variation * 100, 1), texte):
                        nb_nouvelles += 1
            montants_precedents.append(montant)

    # --- Doublons ---
    for fournisseur, groupe in factures.groupby("fournisseur"):
        groupe = groupe.sort_values("date_facture").reset_index(drop=True)
        for i in range(len(groupe) - 1):
            a, b = groupe.iloc[i], groupe.iloc[i + 1]
            meme_montant = abs(float(a["montant_ht"]) - float(b["montant_ht"])) < 0.01
            proches = abs((b["date_facture"] - a["date_facture"]).days) <= 10
            if meme_montant and proches:
                date_str = b["date_facture"].strftime("%Y-%m-%d")
                texte = (
                    f"{fournisseur} : deux factures de {a['montant_ht']:.2f} EUR HT a "
                    f"{a['date_facture'].strftime('%d/%m/%Y')} et {b['date_facture'].strftime('%d/%m/%Y')} "
                    f"(factures {a['numero_facture']} et {b['numero_facture']}) - a verifier, "
                    f"ca ressemble a un doublon."
                )
                if enregistrer_alerte(entreprise_id, "doublon", fournisseur, date_str,
                                       float(a["montant_ht"]), None, texte):
                    nb_nouvelles += 1

    print(f"{nom} : {nb_nouvelles} nouvelle(s) alerte(s) enregistree(s).")

print("\nTermine.")
