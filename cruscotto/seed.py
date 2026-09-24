"""Dati iniziali. Da eseguire una volta sola: python seed.py"""
import sys

import db

FRONTI = [
    ("Paper Storia Globale", "2026-10-15", "parole", 7500, 1300),
    ("Esame Lavenia", "2026-11-16", "libri", 3, 1),
    ("Candidatura CEU Vienna", "2027-01-15", "sezioni", None, 0),  # obiettivo da definire
    ("Tesi magistrale", "2027-02-28", "capitoli", 6, 0),
]


def crea_fronti_iniziali(conn) -> int:
    for nome, scadenza, unita, obiettivo, attuale in FRONTI:
        db.crea_fronte(conn, nome, scadenza, unita, obiettivo, attuale)
    return len(FRONTI)


def main():
    conn = db.connetti()
    if db.fronti(conn, solo_attivi=False):
        # --se-vuoto (usato da avvia.bat): nessun messaggio se i fronti ci sono già.
        if "--se-vuoto" in sys.argv:
            return
        print("Il database contiene già dei fronti: seed non eseguito.")
        sys.exit(1)
    print(f"Creati {crea_fronti_iniziali(conn)} fronti.")


if __name__ == "__main__":
    main()
