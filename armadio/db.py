"""Accesso a SQLite. Le liste si salvano come JSON."""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

import config

_LISTE_CAPO = ("colori", "stagione")
_LISTE_PROFILO = ("palette_consigliata", "colori_da_evitare")

SCHEMA = """
CREATE TABLE IF NOT EXISTS capi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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


def connetti(percorso: Path | str | None = None) -> sqlite3.Connection:
    percorso = Path(percorso or config.DB_PATH)
    percorso.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(percorso, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute("INSERT OR IGNORE INTO profilo (id) VALUES (1)")
    conn.commit()
    return conn


def _adesso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _riga(r: sqlite3.Row | None, liste: tuple[str, ...]) -> dict | None:
    if r is None:
        return None
    d = dict(r)
    for k in liste:
        d[k] = json.loads(d[k] or "[]")
    return d


# --- capi -------------------------------------------------------------------

def aggiungi_capo(conn, capo: dict) -> int:
    cur = conn.execute(
        "INSERT INTO capi (foto_path, categoria, colori, materiale, formalita, stagione, stile, note, aggiunto_il)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (capo.get("foto_path"), capo["categoria"], json.dumps(capo.get("colori", []), ensure_ascii=False),
         capo.get("materiale", ""), int(capo.get("formalita", 3)),
         json.dumps(capo.get("stagione", []), ensure_ascii=False), capo.get("stile", ""),
         capo.get("note", ""), _adesso()),
    )
    conn.commit()
    return cur.lastrowid


def capi(conn) -> list[dict]:
    return [_riga(r, _LISTE_CAPO) for r in conn.execute("SELECT * FROM capi ORDER BY id DESC")]


def capo(conn, capo_id: int) -> dict | None:
    return _riga(conn.execute("SELECT * FROM capi WHERE id = ?", (capo_id,)).fetchone(), _LISTE_CAPO)


def ids_capi(conn) -> set[int]:
    return {r[0] for r in conn.execute("SELECT id FROM capi")}


def elimina_capo(conn, capo_id: int) -> None:
    c = capo(conn, capo_id)
    conn.execute("DELETE FROM capi WHERE id = ?", (capo_id,))
    conn.commit()
    if c and c["foto_path"]:
        (config.BASE / c["foto_path"]).unlink(missing_ok=True)


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


def outfit(conn, outfit_id: int) -> dict | None:
    return _outfit(conn.execute("SELECT * FROM outfit WHERE id = ?", (outfit_id,)).fetchone())


def imposta_giudizio(conn, outfit_id: int, giudizio: str | None) -> None:
    if giudizio is not None and giudizio not in config.GIUDIZI:
        raise ValueError(giudizio)
    conn.execute("UPDATE outfit SET giudizio = ? WHERE id = ?", (giudizio, outfit_id))
    conn.commit()


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
    import re
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
