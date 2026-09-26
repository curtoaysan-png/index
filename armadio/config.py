"""Configurazione di Armadio."""
import os
from pathlib import Path

BASE = Path(__file__).parent

# I dati stanno fuori dalla cartella dell'app, così si può aggiornare l'app senza perderli.
# Windows: C:\Users\<nome>\AppData\Local\Armadio (locale, non sincronizzata da OneDrive).
# Mac/Linux: ~/.armadio
DATI_DIR = Path(os.environ["LOCALAPPDATA"]) / "Armadio" if os.environ.get("LOCALAPPDATA") \
    else Path.home() / ".armadio"
DB_PATH = DATI_DIR / "armadio.db"

# Posizione usata dalla prima versione: al primo avvio database e foto vengono spostati.
VECCHIO_DATI_DIR = BASE / "data"

# Cartella proposta per il backup (si può cambiare dalla pagina Backup).
BACKUP_DIR = DATI_DIR / "backup"

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
