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


def test_aggiorna_ical_non_tocca_manuali_ne_assistente(conn):
    import logica
    from tests.test_logica import ICS
    f = db.crea_fronte(conn, "Paper", "2026-10-15", "parole", 7500)
    db.salva_impegno(conn, "Lezione", "lezione", "2026-09-22T10:00:00", "2026-09-22T12:00:00")
    db.salva_impegno(conn, "Blocco", "blocco di lavoro", "2026-09-23T09:00:00", "2026-09-23T10:30:00",
                     fronte_id=f, origine="assistente")
    da, a = datetime(2026, 9, 21), datetime(2026, 9, 28)
    ev = logica.eventi_da_ical(ICS, da.date(), a.date())
    for _ in range(3):  # aggiornamenti ripetuti: nessun duplicato
        db.sostituisci_ical(conn, ev, da, a)
    tutti = db.impegni(conn)
    assert sorted(i["origine"] for i in tutti) == ["assistente", "ical", "ical", "manuale"]
    assert all(i["fisso"] for i in tutti if i["origine"] == "ical")
    # un evento ical rimosso dal calendario sparisce al prossimo aggiornamento
    db.sostituisci_ical(conn, ev[:1], da, a)
    assert sorted(i["origine"] for i in db.impegni(conn)) == ["assistente", "ical", "manuale"]


def test_scadenza_non_cambia_senza_motivo(conn):
    f = db.crea_fronte(conn, "Paper", "2026-10-15", "parole", 7500)
    for motivo in ("", "   ", None):
        with pytest.raises(ValueError):
            db.cambia_scadenza(conn, f, "2026-10-30", motivo)
    assert db.fronte(conn, f)["scadenza"] == "2026-10-15"
    assert db.rinvii(conn) == []


def test_ogni_cambio_di_scadenza_compare_nei_rinvii(conn):
    f = db.crea_fronte(conn, "Paper", "2026-10-15", "parole", 7500)
    db.cambia_scadenza(conn, f, "2026-10-30", "Turni extra al lavoro")
    db.cambia_scadenza(conn, f, "2026-11-10", "Revisione del relatore")
    r = db.rinvii(conn, f)
    assert [(x["vecchia_scadenza"], x["nuova_scadenza"]) for x in r] == [
        ("2026-10-15", "2026-10-30"), ("2026-10-30", "2026-11-10")]
    assert db.conta_rinvii(conn) == {f: 2}
    assert db.fronte(conn, f)["scadenza"] == "2026-11-10"


def test_backup(conn, tmp_path):
    db.crea_fronte(conn, "Paper", "2026-10-15", "parole", 7500)
    dest = db.esporta_backup(conn, tmp_path / "bk")
    copia = db.connetti(dest)
    assert db.fronti(copia)[0]["nome"] == "Paper"


def test_acquisto_non_si_segna_prima_di_48_ore(conn):
    a = db.aggiungi_acquisto(conn, "Cuffie", 89.9, "tecnologia")
    aggiunto = datetime.fromisoformat(db.acquisti(conn)[0]["aggiunto_il"])
    for stato in ("comprato", "rinunciato"):
        with pytest.raises(ValueError):
            db.decidi_acquisto(conn, a, stato, adesso=aggiunto + timedelta(hours=47, minutes=59))
    assert db.acquisti(conn)[0]["stato"] == "in attesa"
    db.decidi_acquisto(conn, a, "rinunciato", adesso=aggiunto + timedelta(hours=48))
    assert db.acquisti(conn)[0]["stato"] == "rinunciato"
    with pytest.raises(ValueError):  # già deciso
        db.decidi_acquisto(conn, a, "comprato", adesso=aggiunto + timedelta(days=5))


def test_fonti(conn):
    f = db.crea_fronte(conn, "Tesi", "2027-02-28", "capitoli", 6)
    fo = db.aggiungi_fonte(conn, f, "Osterhammel, La trasformazione del mondo")
    db.cambia_stato_fonte(conn, fo, "solo citato")
    assert db.fonti(conn, f)[0]["stato"] == "solo citato"
    with pytest.raises(ValueError):
        db.cambia_stato_fonte(conn, fo, "boh")


def test_database_spostato_fuori_dalla_cartella_app(tmp_path, monkeypatch):
    import config
    vecchio = tmp_path / "app" / "data" / "cruscotto.db"
    nuovo = tmp_path / "AppData" / "Cruscotto" / "cruscotto.db"
    vecchio.parent.mkdir(parents=True)
    c = db.connetti(vecchio)
    db.salva_impegno(c, "Turno", "turno", "2026-09-23T17:00:00", "2026-09-23T22:00:00")
    c.close()
    monkeypatch.setattr(config, "DB_PATH", nuovo)
    monkeypatch.setattr(config, "VECCHIO_DB_PATH", vecchio)

    conn = db.connetti()  # primo avvio: sposta
    assert [i["titolo"] for i in db.impegni(conn)] == ["Turno"]
    assert not vecchio.exists()
    assert vecchio.with_name("cruscotto.db.spostato").exists()  # rinominato, non cancellato
    conn.close()

    # se ricompare un vecchio database, quello nuovo non viene sovrascritto
    db.connetti(vecchio).close()
    assert db.sposta_vecchio_db(nuovo, vecchio) is False
    assert [i["titolo"] for i in db.impegni(db.connetti())] == ["Turno"]


def test_seed_se_vuoto(tmp_path, monkeypatch):
    import sys
    import config
    import seed
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "c.db")
    monkeypatch.setattr(config, "VECCHIO_DB_PATH", tmp_path / "non_esiste.db")
    monkeypatch.setattr(sys, "argv", ["seed.py", "--se-vuoto"])
    seed.main()
    seed.main()  # seconda volta: nessun errore, nessun duplicato
    assert len(db.fronti(db.connetti(), solo_attivi=False)) == 4
