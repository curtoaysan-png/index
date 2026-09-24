"""Configurazione minima del Cruscotto."""
from pathlib import Path

BASE = Path(__file__).parent

# Il database deve stare in una cartella locale, NON su OneDrive in sincronizzazione.
DB_PATH = BASE / "data" / "cruscotto.db"

# Cartella proposta per il backup (si può cambiare dalla pagina Preferenze).
BACKUP_DIR = BASE / "backup"

# Modello usato dall'assistente. La chiave si legge da ANTHROPIC_API_KEY.
MODELLO = "claude-sonnet-5"

# Fascia della giornata in cui calcolare le ore libere (ora di inizio e di fine).
GIORNO_INIZIO = 8
GIORNO_FINE = 22
