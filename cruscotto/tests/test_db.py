from datetime import datetime, timedelta

import pytest

import db

SPIEGAZIONE = (
    "Ho scritto la sezione sul contesto storico. Ho collegato le due fonti principali. "
    "Ho chiarito la domanda di ricerca del paragrafo."
)


def test_sessione_richiede_i_tre_campi(conn):
    f = db.crea_fronte(conn, "Paper", "2026-10-15", "parole", 7500, 1300)
    s = db.avvia_sessione(conn, f, 90)
    with pytest.raises(ValueError):
        db.chiudi_sessione(conn, s, None, SPIEGAZIONE, "Riparto dal cap. 2")
    with pytest.raises(ValueError):
        db.chiudi_sessione(conn, s, 300, "troppo corta", "Riparto dal cap. 2")
    with pytest.raises(ValueError):
        db.chiudi_sessione(conn, s, 300, SPIEGAZIONE, "  ")
    assert db.sessione_in_corso(conn) is not None
    db.chiudi_sessione(conn, s, 300, SPIEGAZIONE, "Riparto dal cap. 2")
    assert db.sessione_in_corso(conn) is None
    assert db.fronte(conn, f)["attuale"] == 1600
    assert db.ultima_ripartenza(conn, f) == "Riparto dal cap. 2"


def test_output_zero_ammesso(conn):
    f = db.crea_fronte(conn, "Tesi", "2027-02-28", "capitoli", 6)
    s = db.avvia_sessione(conn, f, 10)
    db.chiudi_sessione(conn, s, 0, SPIEGAZIONE, "Rileggo l'indice")
    assert db.fronte(conn, f)["attuale"] == 0


def test_una_sola_sessione_in_corso(conn):
    f = db.crea_fronte(conn, "Tesi", "2027-02-28", "capitoli", 6)
    s1 = db.avvia_sessione(conn, f, 90)
    assert db.avvia_sessione(conn, f, 10) == s1
