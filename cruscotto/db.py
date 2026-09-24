"""Accesso al database SQLite. Le regole obbligatorie sono verificate qui."""
import json
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import config

REGOLE_DEFAULT = (
    "Mattina: scrittura originale. Pomeriggio: lavoro tecnico o lettura, mai scrittura "
    "originale. Blocchi da 90 minuti con pausa vera tra un blocco e l'altro. Massimo 3 "
    "blocchi al giorno. Domenica riposo completo. Dopo un turno serale, niente blocchi "
    "prima delle 10."
)

TIPI_IMPEGNO = ["turno", "lezione", "esame", "personale", "blocco di lavoro"]
CATEGORIE_ACQUISTI = ["tecnologia", "giochi", "abbigliamento", "altro"]
STATI_FONTE = ["da leggere", "letto", "estratto", "solo citato"]
MIN_SPIEGAZIONE = 100
ATTESA_ACQUISTI_ORE = 48

SCHEMA = """
CREATE TABLE IF NOT EXISTS fronti (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    scadenza TEXT NOT NULL,
    unita TEXT NOT NULL,
    obiettivo INTEGER,              -- NULL = da definire
    attuale INTEGER NOT NULL DEFAULT 0,
    attivo INTEGER NOT NULL DEFAULT 1,
    creato_il TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessioni (
    id INTEGER PRIMARY KEY,
    fronte_id INTEGER NOT NULL REFERENCES fronti(id),
    inizio TEXT NOT NULL,
    fine TEXT,                      -- NULL = sessione in corso
    durata_prevista_min INTEGER NOT NULL,
    output INTEGER,
    spiegazione TEXT,
    ripartenza TEXT,
    domande TEXT                    -- JSON: domande Feynman sulla spiegazione (v2)
);
CREATE TABLE IF NOT EXISTS rinvii (
    id INTEGER PRIMARY KEY,
    fronte_id INTEGER NOT NULL REFERENCES fronti(id),
    vecchia_scadenza TEXT NOT NULL,
    nuova_scadenza TEXT NOT NULL,
    motivo TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS acquisti (
    id INTEGER PRIMARY KEY,
    oggetto TEXT NOT NULL,
    prezzo REAL NOT NULL,
    categoria TEXT NOT NULL,
    aggiunto_il TEXT NOT NULL,
    stato TEXT NOT NULL DEFAULT 'in attesa',
    deciso_il TEXT
);
CREATE TABLE IF NOT EXISTS impegni (
    id INTEGER PRIMARY KEY,
    titolo TEXT NOT NULL,
    tipo TEXT NOT NULL,
    inizio TEXT NOT NULL,
    fine TEXT NOT NULL,
    ricorrenza TEXT NOT NULL DEFAULT 'nessuna',   -- 'nessuna' / 'settimanale'
    ricorrenza_fine TEXT,                         -- data di fine opzionale
    fronte_id INTEGER REFERENCES fronti(id),
    origine TEXT NOT NULL DEFAULT 'manuale',      -- 'manuale' / 'ical' / 'assistente'
    fisso INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS piani (
    id INTEGER PRIMARY KEY,
    settimana TEXT NOT NULL,
    creato_il TEXT NOT NULL,
    tipo TEXT NOT NULL,
    input_json TEXT NOT NULL,
    proposta_json TEXT,
    spiegazione TEXT,
    stato TEXT NOT NULL DEFAULT 'proposto'
);
CREATE TABLE IF NOT EXISTS preferenze (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    testo_regole TEXT NOT NULL,
    ical_url TEXT
);
CREATE TABLE IF NOT EXISTS fonti (
    id INTEGER PRIMARY KEY,
    fronte_id INTEGER NOT NULL REFERENCES fronti(id),
    titolo TEXT NOT NULL,
    stato TEXT NOT NULL DEFAULT 'da leggere'
);
"""


def _ora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def sposta_vecchio_db(nuovo: Path, vecchio: Path) -> bool:
    """Sposta il database dalla vecchia posizione (dentro la cartella dell'app) alla nuova.

    Solo se la nuova posizione è ancora vuota. Il vecchio file viene rinominato, non cancellato.
    """
    if nuovo.exists() or not vecchio.exists():
        return False
    nuovo.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(vecchio, nuovo)
    vecchio.rename(vecchio.with_name(vecchio.name + ".spostato"))
    return True


def connetti(percorso=None) -> sqlite3.Connection:
    """Apre il database (creandolo se serve) e restituisce la connessione."""
    if percorso is None:
        sposta_vecchio_db(Path(config.DB_PATH), Path(config.VECCHIO_DB_PATH))
    percorso = Path(percorso or config.DB_PATH)
    if str(percorso) != ":memory:":
        percorso.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(percorso), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    # Migrazione per database creati prima della v2.
    colonne = {r["name"] for r in conn.execute("PRAGMA table_info(sessioni)")}
    if "domande" not in colonne:
        conn.execute("ALTER TABLE sessioni ADD COLUMN domande TEXT")
    conn.execute(
        "INSERT OR IGNORE INTO preferenze (id, testo_regole) VALUES (1, ?)", (REGOLE_DEFAULT,)
    )
    conn.commit()
    return conn


def _righe(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


# ---------------------------------------------------------------- fronti

def fronti(conn, solo_attivi=True) -> list[dict]:
    q = "SELECT * FROM fronti"
    if solo_attivi:
        q += " WHERE attivo = 1"
    return _righe(conn.execute(q + " ORDER BY scadenza"))


def fronte(conn, fronte_id) -> dict | None:
    r = conn.execute("SELECT * FROM fronti WHERE id = ?", (fronte_id,)).fetchone()
    return dict(r) if r else None


def crea_fronte(conn, nome, scadenza, unita, obiettivo, attuale=0) -> int:
    if not nome.strip() or not unita.strip():
        raise ValueError("Nome e unità sono obbligatori.")
    cur = conn.execute(
        "INSERT INTO fronti (nome, scadenza, unita, obiettivo, attuale, attivo, creato_il) "
        "VALUES (?, ?, ?, ?, ?, 1, ?)",
        (nome.strip(), str(scadenza), unita.strip(), obiettivo, attuale, _ora()),
    )
    conn.commit()
    return cur.lastrowid


def modifica_fronte(conn, fronte_id, nome, unita, obiettivo, attuale, attivo=True):
    """Modifica i campi del fronte, esclusa la scadenza (vedi cambia_scadenza)."""
    conn.execute(
        "UPDATE fronti SET nome = ?, unita = ?, obiettivo = ?, attuale = ?, attivo = ? WHERE id = ?",
        (nome.strip(), unita.strip(), obiettivo, attuale, int(attivo), fronte_id),
    )
    conn.commit()


def cambia_scadenza(conn, fronte_id, nuova_scadenza, motivo):
    """Cambia la scadenza. Il motivo è obbligatorio e il cambio finisce nei rinvii."""
    if not motivo or not motivo.strip():
        raise ValueError("Per cambiare la scadenza serve un motivo.")
    f = fronte(conn, fronte_id)
    if f is None:
        raise ValueError("Fronte inesistente.")
    nuova = str(nuova_scadenza)
    if nuova == f["scadenza"]:
        return
    conn.execute(
        "INSERT INTO rinvii (fronte_id, vecchia_scadenza, nuova_scadenza, motivo, data) "
        "VALUES (?, ?, ?, ?, ?)",
        (fronte_id, f["scadenza"], nuova, motivo.strip(), _ora()),
    )
    conn.execute("UPDATE fronti SET scadenza = ? WHERE id = ?", (nuova, fronte_id))
    conn.commit()


def rinvii(conn, fronte_id=None) -> list[dict]:
    q = "SELECT r.*, f.nome AS fronte FROM rinvii r JOIN fronti f ON f.id = r.fronte_id"
    args = ()
    if fronte_id is not None:
        q += " WHERE r.fronte_id = ?"
        args = (fronte_id,)
    return _righe(conn.execute(q + " ORDER BY r.data", args))


def conta_rinvii(conn) -> dict[int, int]:
    cur = conn.execute("SELECT fronte_id, COUNT(*) AS n FROM rinvii GROUP BY fronte_id")
    return {r["fronte_id"]: r["n"] for r in cur.fetchall()}


# ---------------------------------------------------------------- sessioni

def sessione_in_corso(conn) -> dict | None:
    r = conn.execute(
        "SELECT s.*, f.nome AS fronte, f.unita FROM sessioni s JOIN fronti f ON f.id = s.fronte_id "
        "WHERE s.fine IS NULL ORDER BY s.id DESC LIMIT 1"
    ).fetchone()
    return dict(r) if r else None


def avvia_sessione(conn, fronte_id, durata_min) -> int:
    """Avvia una sessione. Se ce n'è già una in corso, restituisce quella."""
    aperta = sessione_in_corso(conn)
    if aperta:
        return aperta["id"]
    cur = conn.execute(
        "INSERT INTO sessioni (fronte_id, inizio, durata_prevista_min) VALUES (?, ?, ?)",
        (fronte_id, _ora(), int(durata_min)),
    )
    conn.commit()
    return cur.lastrowid


def annulla_sessione(conn, sessione_id):
    conn.execute("DELETE FROM sessioni WHERE id = ? AND fine IS NULL", (sessione_id,))
    conn.commit()


def chiudi_sessione(conn, sessione_id, output, spiegazione, ripartenza, fine=None, domande=None):
    """Chiude la sessione. Output, spiegazione e ripartenza sono obbligatori.

    `domande` (facoltative) sono le domande Feynman generate sulla spiegazione.
    """
    if output is None or int(output) < 0:
        raise ValueError("L'output è obbligatorio (anche 0).")
    if not spiegazione or len(spiegazione.strip()) < MIN_SPIEGAZIONE:
        raise ValueError(f"La spiegazione deve avere almeno {MIN_SPIEGAZIONE} caratteri.")
    if not ripartenza or not ripartenza.strip():
        raise ValueError("La ripartenza è obbligatoria.")
    s = conn.execute(
        "SELECT * FROM sessioni WHERE id = ? AND fine IS NULL", (sessione_id,)
    ).fetchone()
    if s is None:
        raise ValueError("Sessione non trovata o già chiusa.")
    conn.execute(
        "UPDATE sessioni SET fine = ?, output = ?, spiegazione = ?, ripartenza = ?, domande = ? "
        "WHERE id = ?",
        (fine or _ora(), int(output), spiegazione.strip(), ripartenza.strip(),
         json.dumps(domande, ensure_ascii=False) if domande else None, sessione_id),
    )
    conn.execute(
        "UPDATE fronti SET attuale = attuale + ? WHERE id = ?", (int(output), s["fronte_id"])
    )
    conn.commit()


def sessioni_chiuse(conn, dal=None) -> list[dict]:
    q = (
        "SELECT s.*, f.nome AS fronte, f.unita FROM sessioni s JOIN fronti f ON f.id = s.fronte_id "
        "WHERE s.fine IS NOT NULL"
    )
    args = ()
    if dal is not None:
        q += " AND s.inizio >= ?"
        args = (str(dal),)
    return _righe(conn.execute(q + " ORDER BY s.inizio", args))


def ultima_ripartenza(conn, fronte_id) -> str | None:
    r = conn.execute(
        "SELECT ripartenza FROM sessioni WHERE fronte_id = ? AND fine IS NOT NULL "
        "ORDER BY fine DESC, id DESC LIMIT 1",
        (fronte_id,),
    ).fetchone()
    return r["ripartenza"] if r else None


def ultime_domande(conn, fronte_id) -> list[str]:
    """Domande Feynman dell'ultima sessione chiusa sul fronte (lista vuota se assenti)."""
    r = conn.execute(
        "SELECT domande FROM sessioni WHERE fronte_id = ? AND fine IS NOT NULL "
        "ORDER BY fine DESC, id DESC LIMIT 1",
        (fronte_id,),
    ).fetchone()
    return json.loads(r["domande"]) if r and r["domande"] else []


# ---------------------------------------------------------------- impegni

def impegni(conn) -> list[dict]:
    return _righe(conn.execute(
        "SELECT i.*, f.nome AS fronte FROM impegni i LEFT JOIN fronti f ON f.id = i.fronte_id "
        "ORDER BY i.inizio"
    ))


def impegno(conn, impegno_id) -> dict | None:
    r = conn.execute("SELECT * FROM impegni WHERE id = ?", (impegno_id,)).fetchone()
    return dict(r) if r else None


def salva_impegno(conn, titolo, tipo, inizio, fine, ricorrenza="nessuna", ricorrenza_fine=None,
                  fronte_id=None, origine="manuale", impegno_id=None) -> int:
    """Crea o modifica un impegno. I blocchi di lavoro non sono fissi, tutto il resto sì."""
    if tipo not in TIPI_IMPEGNO:
        raise ValueError(f"Tipo non valido: {tipo}")
    if not titolo.strip():
        raise ValueError("Il titolo è obbligatorio.")
    inizio, fine = str(inizio), str(fine)
    if fine <= inizio:
        raise ValueError("La fine deve essere dopo l'inizio.")
    fisso = 0 if tipo == "blocco di lavoro" else 1
    if tipo != "blocco di lavoro":
        fronte_id = None
    valori = (titolo.strip(), tipo, inizio, fine, ricorrenza,
              str(ricorrenza_fine) if ricorrenza_fine else None, fronte_id, origine, fisso)
    if impegno_id:
        conn.execute(
            "UPDATE impegni SET titolo=?, tipo=?, inizio=?, fine=?, ricorrenza=?, ricorrenza_fine=?, "
            "fronte_id=?, origine=?, fisso=? WHERE id=?",
            valori + (impegno_id,),
        )
        conn.commit()
        return impegno_id
    cur = conn.execute(
        "INSERT INTO impegni (titolo, tipo, inizio, fine, ricorrenza, ricorrenza_fine, fronte_id, "
        "origine, fisso) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        valori,
    )
    conn.commit()
    return cur.lastrowid


def elimina_impegno(conn, impegno_id):
    conn.execute("DELETE FROM impegni WHERE id = ?", (impegno_id,))
    conn.commit()


def sostituisci_ical(conn, eventi, da: datetime, a: datetime) -> int:
    """Sostituisce solo gli impegni con origine 'ical' nell'intervallo. Non tocca gli altri."""
    conn.execute(
        "DELETE FROM impegni WHERE origine = 'ical' AND inizio < ? AND fine > ?",
        (a.isoformat(timespec="seconds"), da.isoformat(timespec="seconds")),
    )
    for e in eventi:
        conn.execute(
            "INSERT INTO impegni (titolo, tipo, inizio, fine, ricorrenza, origine, fisso) "
            "VALUES (?, ?, ?, ?, 'nessuna', 'ical', 1)",
            (e["titolo"], e["tipo"], e["inizio"], e["fine"]),
        )
    conn.commit()
    return len(eventi)


def accetta_blocchi(conn, piano_id, blocchi, fronti_per_nome, sostituisci_da: datetime,
                    sostituisci_a: datetime):
    """Registra i blocchi accettati come impegni 'assistente'.

    Prima rimuove i blocchi dell'assistente tra sostituisci_da e sostituisci_a
    (i blocchi passati restano).
    """
    conn.execute(
        "DELETE FROM impegni WHERE origine = 'assistente' AND inizio >= ? AND inizio < ?",
        (sostituisci_da.isoformat(timespec="seconds"), sostituisci_a.isoformat(timespec="seconds")),
    )
    for b in blocchi:
        conn.execute(
            "INSERT INTO impegni (titolo, tipo, inizio, fine, ricorrenza, fronte_id, origine, fisso) "
            "VALUES (?, 'blocco di lavoro', ?, ?, 'nessuna', ?, 'assistente', 0)",
            (b.get("attivita") or b["fronte"], b["inizio"], b["fine"],
             fronti_per_nome[b["fronte"]]["id"]),
        )
    piano = conn.execute("SELECT proposta_json FROM piani WHERE id = ?", (piano_id,)).fetchone()
    proposta = json.loads(piano["proposta_json"] or "{}")
    proposta["accettati"] = blocchi
    conn.execute(
        "UPDATE piani SET stato = 'accettato', proposta_json = ? WHERE id = ?",
        (json.dumps(proposta, ensure_ascii=False), piano_id),
    )
    conn.commit()


# ---------------------------------------------------------------- piani

def crea_piano(conn, settimana, tipo, input_dati, proposta=None, spiegazione=None) -> int:
    cur = conn.execute(
        "INSERT INTO piani (settimana, creato_il, tipo, input_json, proposta_json, spiegazione, stato) "
        "VALUES (?, ?, ?, ?, ?, ?, 'proposto')",
        (str(settimana), _ora(), tipo, json.dumps(input_dati, ensure_ascii=False),
         json.dumps(proposta, ensure_ascii=False) if proposta is not None else None, spiegazione),
    )
    conn.commit()
    return cur.lastrowid


def piano(conn, piano_id) -> dict | None:
    r = conn.execute("SELECT * FROM piani WHERE id = ?", (piano_id,)).fetchone()
    return dict(r) if r else None


def piani(conn) -> list[dict]:
    return _righe(conn.execute("SELECT * FROM piani ORDER BY settimana DESC, creato_il"))


def rifiuta_piano(conn, piano_id):
    conn.execute("UPDATE piani SET stato = 'rifiutato' WHERE id = ?", (piano_id,))
    conn.commit()


# ---------------------------------------------------------------- preferenze

def preferenze(conn) -> dict:
    return dict(conn.execute("SELECT * FROM preferenze WHERE id = 1").fetchone())


def salva_preferenze(conn, testo_regole=None, ical_url=None):
    p = preferenze(conn)
    conn.execute(
        "UPDATE preferenze SET testo_regole = ?, ical_url = ? WHERE id = 1",
        (testo_regole if testo_regole is not None else p["testo_regole"],
         ical_url if ical_url is not None else p["ical_url"]),
    )
    conn.commit()


# ---------------------------------------------------------------- acquisti

def aggiungi_acquisto(conn, oggetto, prezzo, categoria) -> int:
    if not oggetto.strip():
        raise ValueError("L'oggetto è obbligatorio.")
    cur = conn.execute(
        "INSERT INTO acquisti (oggetto, prezzo, categoria, aggiunto_il, stato) "
        "VALUES (?, ?, ?, ?, 'in attesa')",
        (oggetto.strip(), float(prezzo), categoria, _ora()),
    )
    conn.commit()
    return cur.lastrowid


def acquisti(conn) -> list[dict]:
    return _righe(conn.execute("SELECT * FROM acquisti ORDER BY aggiunto_il DESC"))


def decidi_acquisto(conn, acquisto_id, stato, adesso: datetime | None = None):
    """Segna 'comprato' o 'rinunciato', solo dopo 48 ore dall'inserimento."""
    if stato not in ("comprato", "rinunciato"):
        raise ValueError("Stato non valido.")
    adesso = adesso or datetime.now()
    a = conn.execute("SELECT * FROM acquisti WHERE id = ?", (acquisto_id,)).fetchone()
    if a is None or a["stato"] != "in attesa":
        raise ValueError("Acquisto non in attesa.")
    if adesso < datetime.fromisoformat(a["aggiunto_il"]) + timedelta(hours=ATTESA_ACQUISTI_ORE):
        raise ValueError("Non sono ancora passate 48 ore.")
    conn.execute(
        "UPDATE acquisti SET stato = ?, deciso_il = ? WHERE id = ?",
        (stato, adesso.isoformat(timespec="seconds"), acquisto_id),
    )
    conn.commit()


# ---------------------------------------------------------------- fonti

def fonti(conn, fronte_id=None) -> list[dict]:
    q = "SELECT fo.*, f.nome AS fronte FROM fonti fo JOIN fronti f ON f.id = fo.fronte_id"
    args = ()
    if fronte_id is not None:
        q += " WHERE fo.fronte_id = ?"
        args = (fronte_id,)
    return _righe(conn.execute(q + " ORDER BY f.nome, fo.titolo", args))


def aggiungi_fonte(conn, fronte_id, titolo, stato="da leggere") -> int:
    if not titolo.strip():
        raise ValueError("Il titolo è obbligatorio.")
    cur = conn.execute(
        "INSERT INTO fonti (fronte_id, titolo, stato) VALUES (?, ?, ?)",
        (fronte_id, titolo.strip(), stato),
    )
    conn.commit()
    return cur.lastrowid


def cambia_stato_fonte(conn, fonte_id, stato):
    if stato not in STATI_FONTE:
        raise ValueError("Stato non valido.")
    conn.execute("UPDATE fonti SET stato = ? WHERE id = ?", (stato, fonte_id))
    conn.commit()


def elimina_fonte(conn, fonte_id):
    conn.execute("DELETE FROM fonti WHERE id = ?", (fonte_id,))
    conn.commit()


# ---------------------------------------------------------------- backup

def esporta_backup(conn, cartella) -> Path:
    """Salva una copia coerente del database con la data nel nome."""
    cartella = Path(cartella).expanduser()
    cartella.mkdir(parents=True, exist_ok=True)
    dest = cartella / f"cruscotto_{datetime.now():%Y-%m-%d_%H%M}.db"
    copia = sqlite3.connect(str(dest))
    with copia:
        conn.backup(copia)
    copia.close()
    return dest

