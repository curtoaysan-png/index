"""Configurazione minima del Cruscotto."""
import os
from pathlib import Path

BASE = Path(__file__).parent

# I dati stanno fuori dalla cartella dell'app, così si può aggiornare l'app senza perderli.
# Windows: C:\Users\<nome>\AppData\Local\Cruscotto (locale, non sincronizzata da OneDrive).
# Mac/Linux: ~/.cruscotto
DATI_DIR = Path(os.environ["LOCALAPPDATA"]) / "Cruscotto" if os.environ.get("LOCALAPPDATA") \
    else Path.home() / ".cruscotto"
DB_PATH = DATI_DIR / "cruscotto.db"

# Posizione usata fino alla versione precedente: al primo avvio il database viene spostato.
VECCHIO_DB_PATH = BASE / "data" / "cruscotto.db"

# Cartella proposta per il backup (si può cambiare dalla pagina Preferenze).
BACKUP_DIR = DATI_DIR / "backup"

# Modello usato dall'assistente. La chiave si legge da ANTHROPIC_API_KEY.
MODELLO = "claude-sonnet-5"

# Fascia della giornata in cui calcolare le ore libere (ora di inizio e di fine).
GIORNO_INIZIO = 8
GIORNO_FINE = 22
