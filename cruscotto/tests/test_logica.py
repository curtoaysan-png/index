from datetime import date, datetime, timedelta

import logica

OGGI = date(2026, 9, 24)
PAPER = {"id": 1, "nome": "Paper", "scadenza": "2026-10-15", "obiettivo": 7500, "attuale": 1300,
         "attivo": 1, "unita": "parole"}


def sess(giorno: date, output, fronte_id=1):
    ini = datetime.combine(giorno, datetime.min.time()).replace(hour=9)
    return {"fronte_id": fronte_id, "inizio": ini.isoformat(), "fine": (ini + timedelta(minutes=90)).isoformat(),
            "output": output}


# ---------------------------------------------------------------- ritmo e proiezione

def test_ritmo_medio_ultimi_7_giorni():
    sessioni = [sess(OGGI, 700), sess(OGGI - timedelta(days=6), 700),
                sess(OGGI - timedelta(days=7), 5000),       # fuori finestra
                sess(OGGI, 999, fronte_id=2)]               # altro fronte
    assert logica.ritmo_medio(sessioni, 1, OGGI) == 200


def test_nessuna_sessione_ritmo_zero_senza_errori():
    p = logica.proiezione(PAPER, [], OGGI)
    assert p["ritmo_attuale"] == 0
    assert p["data_stimata"] is None
    assert p["colore"] == "rosso"
    assert p["ritmo_necessario"] == 6200 / 21


def test_data_stimata_e_verde():
    # 7 sessioni da 1000 -> 1000/giorno -> 6200 rimanenti = 7 giorni
    sessioni = [sess(OGGI - timedelta(days=i), 1000) for i in range(7)]
    p = logica.proiezione(PAPER, sessioni, OGGI)
    assert p["ritmo_attuale"] == 1000
    assert p["data_stimata"] == OGGI + timedelta(days=7)
    assert p["colore"] == "verde"


def test_arrotondamento_per_eccesso():
    sessioni = [sess(OGGI, 7 * 300)]  # 300/giorno -> 6200/300 = 20,67 -> 21 giorni
    p = logica.proiezione(PAPER, sessioni, OGGI)
    assert p["data_stimata"] == OGGI + timedelta(days=21)
    assert p["data_stimata"] == date(2026, 10, 15)
    assert p["colore"] == "giallo"


def test_colori():
    scad = date(2026, 10, 15)
    assert logica.colore_proiezione(date(2026, 10, 11), scad) == "verde"
    assert logica.colore_proiezione(date(2026, 10, 12), scad) == "giallo"
    assert logica.colore_proiezione(date(2026, 10, 15), scad) == "giallo"
    assert logica.colore_proiezione(date(2026, 10, 16), scad) == "rosso"
    assert logica.colore_proiezione(None, scad) == "rosso"


def test_obiettivo_da_definire_e_completato():
    p = logica.proiezione({**PAPER, "obiettivo": None}, [], OGGI)
    assert p["colore"] == "grigio" and p["data_stimata"] is None
    p = logica.proiezione({**PAPER, "attuale": 7500}, [], OGGI)
    assert p["completato"] and p["colore"] == "verde"


def test_scadenza_passata_non_divide_per_zero():
    p = logica.proiezione({**PAPER, "scadenza": "2026-09-20"}, [], OGGI)
    assert p["giorni_mancanti"] == -4
    assert p["ritmo_necessario"] == 6200


def test_catena_giorni():
    catena = logica.catena_giorni([sess(OGGI, 10), sess(OGGI - timedelta(days=3), 0)], OGGI)
    assert len(catena) == 14
    assert catena[-1] == (OGGI, True)
    assert catena[-4] == (OGGI - timedelta(days=3), True)
    assert sum(p for _, p in catena) == 2
