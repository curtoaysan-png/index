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


# ---------------------------------------------------------------- calendario

def imp(id_, inizio, fine, tipo="turno", ricorrenza="nessuna", ricorrenza_fine=None, origine="manuale"):
    return {"id": id_, "titolo": f"imp{id_}", "tipo": tipo, "inizio": inizio, "fine": fine,
            "ricorrenza": ricorrenza, "ricorrenza_fine": ricorrenza_fine, "origine": origine,
            "fisso": 0 if tipo == "blocco di lavoro" else 1, "fronte_id": None}


def test_turno_settimanale_fino_alla_data_di_fine():
    turno = imp(1, "2026-09-02T17:00:00", "2026-09-02T22:00:00", ricorrenza="settimanale",
                ricorrenza_fine="2026-10-21")
    occ = logica.espandi_impegni([turno], date(2026, 9, 1), date(2026, 12, 31))
    giorni = [o["inizio_dt"].date() for o in occ]
    assert giorni[0] == date(2026, 9, 2)
    assert giorni[-1] == date(2026, 10, 21)
    assert len(giorni) == 8  # tutti i mercoledì dal 2/9 al 21/10
    # compare in ogni settimana successiva fino alla fine
    for sett in range(8):
        lun = date(2026, 8, 31) + timedelta(weeks=sett)
        assert len(logica.espandi_impegni([turno], lun, lun + timedelta(days=7))) == 1
    assert logica.espandi_impegni([turno], date(2026, 10, 26), date(2026, 11, 2)) == []


def test_settimanale_senza_fine_e_prima_dell_inizio():
    lezione = imp(2, "2026-09-07T10:00:00", "2026-09-07T12:00:00", "lezione", "settimanale")
    assert len(logica.espandi_impegni([lezione], date(2027, 3, 1), date(2027, 3, 8))) == 1
    assert logica.espandi_impegni([lezione], date(2026, 8, 31), date(2026, 9, 7)) == []


def test_fasce_libere_e_riepilogo():
    lun = date(2026, 9, 21)
    impegni = [imp(1, "2026-09-21T09:00:00", "2026-09-21T13:00:00"),
               imp(2, "2026-09-21T15:00:00", "2026-09-21T16:30:00", tipo="blocco di lavoro")]
    occ = logica.espandi_impegni(impegni, lun, lun + timedelta(days=7))
    libere = logica.fasce_libere([o for o in occ if o["fisso"]], lun, ora_inizio=8, ora_fine=22)
    assert libere[lun] == [(datetime(2026, 9, 21, 8), datetime(2026, 9, 21, 9)),
                           (datetime(2026, 9, 21, 13), datetime(2026, 9, 21, 22))]
    r = logica.riepilogo_settimana(occ, [], lun)
    assert r["ore_fisse"] == 4
    assert r["ore_blocchi"] == 1.5
    assert r["ore_libere"] == 7 * 14 - 4


ICS = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//test//
BEGIN:VEVENT
UID:1
SUMMARY:Turno bar
DTSTART:20260922T170000
DTEND:20260922T220000
RRULE:FREQ=WEEKLY;COUNT=3
END:VEVENT
BEGIN:VEVENT
UID:2
SUMMARY:Compleanno
DTSTART;VALUE=DATE:20260923
DTEND;VALUE=DATE:20260924
END:VEVENT
BEGIN:VEVENT
UID:3
SUMMARY:Lezione storia
DTSTART:20260924T100000
DTEND:20260924T120000
END:VEVENT
END:VCALENDAR
"""


def test_eventi_da_ical():
    ev = logica.eventi_da_ical(ICS, date(2026, 9, 21), date(2026, 9, 28))
    assert [(e["titolo"], e["tipo"], e["inizio"]) for e in ev] == [
        ("Turno bar", "turno", "2026-09-22T17:00:00"),
        ("Lezione storia", "lezione", "2026-09-24T10:00:00"),
    ]
    # la ricorrenza compare anche nella settimana successiva
    assert len(logica.eventi_da_ical(ICS, date(2026, 9, 28), date(2026, 10, 5))) == 1


# ---------------------------------------------------------------- acquisti

def test_attesa_residua():
    agg = "2026-09-24T10:00:00"
    assert logica.attesa_residua(agg, datetime(2026, 9, 26, 9, 0)) == timedelta(hours=1)
    assert logica.attesa_residua(agg, datetime(2026, 9, 26, 10, 0)) <= timedelta(0)


def test_riepilogo_acquisti_mese():
    acquisti = [
        {"prezzo": 60.0, "categoria": "giochi", "stato": "rinunciato", "deciso_il": "2026-09-10T10:00:00"},
        {"prezzo": 40.0, "categoria": "giochi", "stato": "comprato", "deciso_il": "2026-09-11T10:00:00"},
        {"prezzo": 100.0, "categoria": "tecnologia", "stato": "rinunciato", "deciso_il": "2026-09-12T10:00:00"},
        {"prezzo": 999.0, "categoria": "tecnologia", "stato": "rinunciato", "deciso_il": "2026-08-30T10:00:00"},
        {"prezzo": 5.0, "categoria": "altro", "stato": "in attesa", "deciso_il": None},
    ]
    r = logica.riepilogo_acquisti_mese(acquisti, 2026, 9)
    assert r["rinunciato"] == 160 and r["comprato"] == 40
    assert r["per_categoria"] == {"giochi": {"comprato": 40, "rinunciato": 60},
                                  "tecnologia": {"comprato": 0, "rinunciato": 100}}


def test_fronte_piu_vicino_salta_quelli_completati():
    completato = {**PAPER, "id": 9, "scadenza": "2026-10-01", "attuale": 7500}
    archiviato = {**PAPER, "id": 8, "scadenza": "2026-09-30", "attivo": 0}
    senza_obiettivo = {**PAPER, "id": 7, "scadenza": "2027-01-15", "obiettivo": None}
    assert logica.fronte_piu_vicino([completato, archiviato, PAPER, senza_obiettivo])["id"] == 1
    assert logica.fronte_piu_vicino([completato]) is None


def test_url_webcal():
    assert logica.normalizza_url_ical(" webcal://calendar.google.com/x.ics ") == "https://calendar.google.com/x.ics"
    assert logica.normalizza_url_ical("https://a/b.ics") == "https://a/b.ics"
