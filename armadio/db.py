"""Accesso al database. Le liste si salvano come JSON, le foto come byte (JPEG).

Sul PC il database è un file SQLite. Nel cloud (variabile DATABASE_URL impostata) è Postgres:
le query sono le stesse, `ConnessionePg` traduce i segnaposto e restituisce gli id inseriti.
"""
import json
import os
import re
import shutil
import sqlite3
import tempfile
import threading
from datetime import datetime
from pathlib import Path

import config

_LISTE_CAPO = ("colori", "stagione")
_LISTE_PROFILO = ("palette_consigliata", "colori_da_evitare")
_CAMPI_CAPO = "id, categoria, colori, materiale, formalita, stagione, stile, note, aggiunto_il"

SCHEMA = """
CREATE TABLE IF NOT EXISTS capi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    foto BLOB,
    foto_path TEXT,
    categoria TEXT NOT NULL,
    colori TEXT NOT NULL DEFAULT '[]',
    materiale TEXT DEFAULT '',
    formalita INTEGER DEFAULT 3,
    stagione TEXT NOT NULL DEFAULT '[]',
    stile TEXT DEFAULT '',
    note TEXT DEFAULT '',
    aggiunto_il TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS profilo (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    stagione_armocromia TEXT DEFAULT '',
    seconda_stagione TEXT DEFAULT '',
    sottotono TEXT DEFAULT '',
    palette_consigliata TEXT NOT NULL DEFAULT '[]',
    colori_da_evitare TEXT NOT NULL DEFAULT '[]',
    affidabilita TEXT DEFAULT '',
    note_armocromia TEXT DEFAULT '',
    preferenze_stile TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS outfit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    richiesta TEXT NOT NULL,
    capi_ids TEXT NOT NULL DEFAULT '[]',
    spiegazione TEXT DEFAULT '',
    stile_suggerito TEXT DEFAULT '',
    dettagli TEXT NOT NULL DEFAULT '{}',
    creato_il TEXT NOT NULL,
    giudizio TEXT
);
"""

TABELLE = ["profilo", "capi", "outfit"]


def url_database() -> str | None:
    """Indirizzo del database Postgres (cloud), oppure None per usare SQLite sul PC."""
    return os.environ.get("DATABASE_URL", "").strip() or None


def in_cloud() -> bool:
    return url_database() is not None


_sqlite = {}
_sqlite_lock = threading.Lock()


def connetti(percorso: Path | str | None = None):
    """Apre il database (creandolo se serve) e restituisce la connessione.

    Con `percorso` si apre sempre quel file SQLite (test, backup); altrimenti Postgres se
    DATABASE_URL è impostata, se no il file SQLite in config.DB_PATH (una connessione per processo).
    """
    if percorso is None and in_cloud():
        return _connessione_pg(url_database())
    if percorso is not None:
        return _apri_sqlite(Path(percorso))
    with _sqlite_lock:
        chiave = str(config.DB_PATH)
        if chiave not in _sqlite:
            sposta_vecchi_dati(Path(config.DB_PATH), Path(config.VECCHIO_DATI_DIR))
            _sqlite[chiave] = _apri_sqlite(Path(config.DB_PATH))
        return _sqlite[chiave]


def _apri_sqlite(percorso: Path) -> sqlite3.Connection:
    percorso.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(percorso, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    colonne = {r["name"] for r in conn.execute("PRAGMA table_info(capi)")}
    if "foto" not in colonne:  # database della prima versione: foto come file
        conn.execute("ALTER TABLE capi ADD COLUMN foto BLOB")
    _profilo_iniziale(conn)
    return conn


def _profilo_iniziale(conn):
    conn.execute("INSERT INTO profilo (id) VALUES (1) ON CONFLICT DO NOTHING")
    conn.commit()


def sposta_vecchi_dati(nuovo_db: Path, vecchia_dir: Path) -> bool:
    """Porta il database della prima versione (armadio/data) nella nuova posizione.

    Solo se la nuova posizione è ancora vuota. Le foto, che erano file, entrano nel database.
    Il vecchio database viene rinominato, non cancellato.
    """
    vecchio_db = vecchia_dir / "armadio.db"
    if nuovo_db.exists() or not vecchio_db.exists():
        return False
    nuovo_db.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(vecchio_db, nuovo_db)
    conn = _apri_sqlite(nuovo_db)
    for r in conn.execute("SELECT id, foto_path FROM capi WHERE foto IS NULL AND foto_path IS NOT NULL").fetchall():
        file = vecchia_dir.parent / r["foto_path"]
        if file.exists():
            conn.execute("UPDATE capi SET foto = ? WHERE id = ?", (file.read_bytes(), r["id"]))
    conn.commit()
    conn.close()
    vecchio_db.rename(vecchio_db.with_name(vecchio_db.name + ".spostato"))
    return True


# ---------------------------------------------------------------- Postgres (cloud)

class _Risultato:
    """Risultato di una query Postgres con la stessa interfaccia usata per SQLite."""

    def __init__(self, righe, lastrowid=None):
        self._righe = righe
        self.lastrowid = lastrowid

    def fetchone(self):
        return self._righe[0] if self._righe else None

    def fetchall(self):
        return self._righe

    def __iter__(self):
        return iter(self._righe)


class ConnessionePg:
    """Connessione Postgres che accetta le query scritte per SQLite (segnaposto `?`)."""

    def __init__(self, url):
        import psycopg
        from psycopg.rows import dict_row

        self._conn = psycopg.connect(url, row_factory=dict_row)
        self._lock = threading.RLock()
        self._scrittura = False  # True tra una modifica e il suo commit

    def execute(self, sql, parametri=()):
        sql = sql.replace("?", "%s")
        lettura = sql.lstrip().upper().startswith("SELECT")
        inserimento = sql.lstrip().upper().startswith("INSERT") and "RETURNING" not in sql.upper()
        if inserimento and "ON CONFLICT" not in sql.upper():
            sql += " RETURNING id"
        else:
            inserimento = False
        with self._lock:
            try:
                cur = self._conn.execute(sql, parametri)
                righe = cur.fetchall() if cur.description else []
            except Exception:
                self._conn.rollback()  # altrimenti la transazione resta bloccata
                self._scrittura = False
                raise
            if not lettura:
                self._scrittura = True
            elif not self._scrittura:
                # Una lettura da sola non deve lasciare una transazione aperta: bloccherebbe
                # altre operazioni sulle tabelle (il database può essere condiviso col Cruscotto).
                self._conn.commit()
        if inserimento:
            return _Risultato([], righe[0]["id"])
        return _Risultato(righe)

    def commit(self):
        with self._lock:
            self._conn.commit()
            self._scrittura = False

    @property
    def in_transazione(self) -> bool:
        from psycopg.pq import TransactionStatus
        return self._conn.info.transaction_status != TransactionStatus.IDLE

    def close(self):
        self._conn.close()

    @property
    def chiusa(self) -> bool:
        return self._conn.closed


def schema_pg() -> str:
    schema = SCHEMA.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
    return re.sub(r"\bBLOB\b", "BYTEA", schema)


_pg = {}
_pg_lock = threading.Lock()


def _connessione_pg(url) -> ConnessionePg:
    """Una sola connessione per processo, riaperta se il server l'ha chiusa (inattività)."""
    with _pg_lock:
        conn = _pg.get(url)
        if conn is not None and not conn.chiusa:
            try:
                conn.execute("SELECT 1")
                return conn
            except Exception:
                conn.close()
        conn = ConnessionePg(url)
        for istruzione in schema_pg().split(";"):
            if istruzione.strip():
                conn.execute(istruzione)
        _profilo_iniziale(conn)
        _pg[url] = conn
        return conn


def _adesso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _riga(r, liste: tuple[str, ...]) -> dict | None:
    if r is None:
        return None
    d = dict(r)
    for k in liste:
        d[k] = json.loads(d[k] or "[]")
    return d


# --- capi -------------------------------------------------------------------

def aggiungi_capo(conn, capo: dict) -> int:
    cur = conn.execute(
        "INSERT INTO capi (foto, categoria, colori, materiale, formalita, stagione, stile, note, aggiunto_il)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (capo.get("foto"), capo["categoria"], json.dumps(capo.get("colori", []), ensure_ascii=False),
         capo.get("materiale", ""), int(capo.get("formalita", 3)),
         json.dumps(capo.get("stagione", []), ensure_ascii=False), capo.get("stile", ""),
         capo.get("note", ""), _adesso()),
    )
    conn.commit()
    return cur.lastrowid


def capi(conn) -> list[dict]:
    """Tutti i capi, senza le foto (si leggono a parte con foto_capo)."""
    return [_riga(r, _LISTE_CAPO) for r in conn.execute(f"SELECT {_CAMPI_CAPO} FROM capi ORDER BY id DESC")]


def capo(conn, capo_id: int) -> dict | None:
    r = conn.execute(f"SELECT {_CAMPI_CAPO} FROM capi WHERE id = ?", (capo_id,)).fetchone()
    return _riga(r, _LISTE_CAPO)


def foto_capo(conn, capo_id: int) -> bytes | None:
    r = conn.execute("SELECT foto FROM capi WHERE id = ?", (capo_id,)).fetchone()
    return bytes(r["foto"]) if r and r["foto"] is not None else None


def ids_capi(conn) -> set[int]:
    return {r["id"] for r in conn.execute("SELECT id FROM capi")}


def elimina_capo(conn, capo_id: int) -> None:
    conn.execute("DELETE FROM capi WHERE id = ?", (capo_id,))
    conn.commit()


# --- profilo ----------------------------------------------------------------

def profilo(conn) -> dict:
    return _riga(conn.execute("SELECT * FROM profilo WHERE id = 1").fetchone(), _LISTE_PROFILO)


def aggiorna_profilo(conn, **campi) -> None:
    ammessi = {"stagione_armocromia", "seconda_stagione", "sottotono", "palette_consigliata",
               "colori_da_evitare", "affidabilita", "note_armocromia", "preferenze_stile"}
    valori = {}
    for k, v in campi.items():
        if k not in ammessi:
            raise KeyError(k)
        valori[k] = json.dumps(v, ensure_ascii=False) if k in _LISTE_PROFILO else v
    if valori:
        assegna = ", ".join(f"{k} = ?" for k in valori)
        conn.execute(f"UPDATE profilo SET {assegna} WHERE id = 1", list(valori.values()))
        conn.commit()


# --- outfit -----------------------------------------------------------------

def _outfit(r):
    if r is None:
        return None
    d = dict(r)
    d["capi_ids"] = json.loads(d["capi_ids"] or "[]")
    d["dettagli"] = json.loads(d["dettagli"] or "{}")
    return d


def salva_outfit(conn, richiesta: str, capi_ids: list[int], spiegazione: str,
                 stile_suggerito: str, dettagli: dict) -> int:
    cur = conn.execute(
        "INSERT INTO outfit (richiesta, capi_ids, spiegazione, stile_suggerito, dettagli, creato_il)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (richiesta, json.dumps(capi_ids), spiegazione, stile_suggerito,
         json.dumps(dettagli, ensure_ascii=False), _adesso()),
    )
    conn.commit()
    return cur.lastrowid


def outfit_recenti(conn, n: int = 10) -> list[dict]:
    return [_outfit(r) for r in conn.execute("SELECT * FROM outfit ORDER BY id DESC LIMIT ?", (n,))]


def conta_outfit(conn) -> int:
    return conn.execute("SELECT COUNT(*) AS n FROM outfit").fetchone()["n"]


def outfit(conn, outfit_id: int) -> dict | None:
    return _outfit(conn.execute("SELECT * FROM outfit WHERE id = ?", (outfit_id,)).fetchone())


def imposta_giudizio(conn, outfit_id: int, giudizio: str | None) -> None:
    if giudizio is not None and giudizio not in config.GIUDIZI:
        raise ValueError(giudizio)
    conn.execute("UPDATE outfit SET giudizio = ? WHERE id = ?", (giudizio, outfit_id))
    conn.commit()


# ---------------------------------------------------------------- backup e ripristino

def _colonne(conn, tabella) -> list[str]:
    if isinstance(conn, ConnessionePg):
        righe = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = ?", (tabella,))
        return [r["column_name"] for r in righe]
    return [r["name"] for r in conn.execute(f"PRAGMA table_info({tabella})")]


def _copia_tabelle(sorgente, destinazione):
    """Sostituisce tutti i dati di `destinazione` con quelli di `sorgente` (stessi id)."""
    for tabella in TABELLE:
        destinazione.execute(f"DELETE FROM {tabella}")
    for tabella in TABELLE:
        colonne_dest = set(_colonne(destinazione, tabella))
        for r in sorgente.execute(f"SELECT * FROM {tabella}").fetchall():
            r = {k: v for k, v in dict(r).items() if k in colonne_dest}
            if isinstance(r.get("foto"), memoryview):
                r["foto"] = bytes(r["foto"])
            destinazione.execute(
                f"INSERT INTO {tabella} ({', '.join(r)}) VALUES ({', '.join('?' for _ in r)}) "
                "ON CONFLICT DO NOTHING",
                tuple(r.values()),
            )
    if isinstance(destinazione, ConnessionePg):
        for tabella in ("capi", "outfit"):
            destinazione.execute(
                f"SELECT setval(pg_get_serial_sequence('{tabella}', 'id'), "
                f"COALESCE((SELECT MAX(id) FROM {tabella}), 0) + 1, false)")
    _profilo_iniziale(destinazione)  # garantisce la riga del profilo; fa anche il commit


def nome_backup() -> str:
    return f"armadio_{datetime.now():%Y-%m-%d_%H%M}.db"


def backup_in_byte(conn) -> bytes:
    """Copia completa dei dati, foto comprese, in un file SQLite restituito come byte."""
    with tempfile.TemporaryDirectory() as cartella:
        percorso = Path(cartella) / "backup.db"
        copia = connetti(percorso)
        _copia_tabelle(conn, copia)
        copia.close()
        return percorso.read_bytes()


def esporta_backup(conn, cartella) -> Path:
    """Salva una copia del database con la data nel nome."""
    cartella = Path(cartella).expanduser()
    cartella.mkdir(parents=True, exist_ok=True)
    dest = cartella / nome_backup()
    dest.write_bytes(backup_in_byte(conn))
    return dest


def ripristina_backup(conn, contenuto: bytes):
    """Sostituisce TUTTI i dati attuali con quelli di un file di backup."""
    if not contenuto.startswith(b"SQLite format 3"):
        raise ValueError("Il file non è un backup di Armadio.")
    with tempfile.TemporaryDirectory() as cartella:
        percorso = Path(cartella) / "ripristino.db"
        percorso.write_bytes(contenuto)
        try:
            grezzo = sqlite3.connect(percorso)
            tabelle = {r[0] for r in grezzo.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            grezzo.close()
        except sqlite3.DatabaseError as e:
            raise ValueError("Il file non è un backup di Armadio.") from e
        if "capi" not in tabelle:
            raise ValueError("Il file non è un backup di Armadio.")
        sorgente = connetti(percorso)
        try:
            _copia_tabelle(sorgente, conn)
        finally:
            sorgente.close()


# --- colori in forma di testo (per la modifica a mano) -----------------------

def colori_a_testo(colori: list) -> str:
    righe = []
    for c in colori:
        if isinstance(c, dict):
            righe.append(f"{c.get('nome', '')} {c.get('hex', '')}".strip())
        else:
            righe.append(str(c))
    return "\n".join(righe)


def testo_a_colori(testo: str) -> list[dict]:
    """Una riga per colore: "nome #RRGGBB" (il codice è facoltativo)."""
    colori = []
    for riga in testo.splitlines():
        riga = riga.strip()
        if not riga:
            continue
        m = re.search(r"#[0-9a-fA-F]{6}\b", riga)
        hex_ = m.group(0).upper() if m else ""
        nome = (riga[:m.start()] + riga[m.end():]).strip(" -:,") if m else riga
        colori.append({"nome": nome or hex_, "hex": hex_})
    return colori
