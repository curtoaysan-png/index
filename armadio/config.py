"""Configurazione di Armadio."""
from pathlib import Path

BASE = Path(__file__).parent
DATI_DIR = BASE / "data"
FOTO_DIR = DATI_DIR / "foto"
DB_PATH = DATI_DIR / "armadio.db"

# Modello usato per tutte le chiamate. La chiave si legge da ANTHROPIC_API_KEY.
MODELLO = "claude-sonnet-5"

# Lato lungo massimo delle foto salvate e inviate (riduce i costi).
LATO_MAX = 1024

CATEGORIE = ["top", "pantaloni", "gonna", "vestito", "capospalla", "scarpe", "accessorio"]
STAGIONI = ["primavera", "estate", "autunno", "inverno"]
STILI = ["casual", "smart casual", "minimal", "classico", "elegante", "sportivo", "romantico", "boho"]
GIUDIZI = ["mi piace", "non mi piace", "indossato"]

STAGIONI_ARMOCROMIA = [
    "primavera chiara", "primavera calda", "primavera brillante",
    "estate chiara", "estate fredda", "estate soft",
    "autunno soft", "autunno caldo", "autunno profondo",
    "inverno profondo", "inverno freddo", "inverno brillante",
]
SOTTOTONI = ["caldo", "freddo", "neutro", "olivastro"]
