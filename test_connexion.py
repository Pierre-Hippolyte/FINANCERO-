import os
import sys

import httpx
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_KEY")

if not url or not key:
    print("Erreur : SUPABASE_URL et/ou SUPABASE_SERVICE_KEY manquent dans .env")
    sys.exit(1)

try:
    create_client(url, key)
    response = httpx.get(
        f"{url}/rest/v1/",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        timeout=10,
    )
    if response.status_code == 200:
        print("Connexion a Supabase reussie.")
    else:
        print(f"Echec de la connexion a Supabase : HTTP {response.status_code}")
        sys.exit(1)
except Exception as exc:
    print(f"Echec de la connexion a Supabase : {exc}")
    sys.exit(1)
