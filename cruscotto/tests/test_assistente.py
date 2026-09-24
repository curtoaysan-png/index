"""Assistente: verifica dei blocchi su una risposta simulata, senza chiamare l'API."""
import json
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

import assistente
import db
import logica

LUNEDI = date(2026, 9, 28)
ADESSO = datetime(2026, 9, 27, 20, 0)
FRONTI = [{"id": 1, "nome": "Paper Storia Globale", "scadenza": "2026-10-15", "unita": "parole",
           "obiettivo": 7500, "attuale": 1300, "attivo": 1},
          {"id": 2, "nome": "Esame Lavenia", "scadenza": "2026-11-16", "unita": "libri",
           "obiettivo": 3, "attuale": 1, "attivo": 1}]
IMPEGNI = [
    {"id": 1, "titolo": "Turno bar", "tipo": "turno", "inizio": "2026-09-02T17:00:00",
     "fine": "2026-09-02T22:00:00", "ricorrenza": "settimanale", "ricorrenza_fine": None,
     "fronte_id": None, "origine": "manuale", "fisso": 1},
    {"id": 2, "titolo": "Lezione", "tipo": "lezione", "inizio": "2026-09-28T10:00:00",
     "fine": "2026-09-28T12:00:00", "ricorrenza": "nessuna", "ricorrenza_fine": None,
     "fronte_id": None, "origine": "manuale", "fisso": 1},
]

RISPOSTA = {
    "blocchi": [
        {"fronte": "Paper Storia Globale", "inizio": "2026-09-28T08:30", "fine": "2026-09-28T10:00",
         "attivita": "Segato → blocco cap. 1"},                                  # ok
        {"fronte": "Paper Storia Globale", "inizio": "2026-09-28T11:00", "fine": "2026-09-28T12:30",
         "attivita": "sopra la lezione"},                                       # conflitto
        {"fronte": "Esame Lavenia", "inizio": "2026-09-30T18:00", "fine": "2026-09-30T19:30",
         "attivita": "sopra il turno ricorrente"},                              # conflitto
        {"fronte": "Esame Lavenia", "inizio": "2026-09-29T15:00", "fine": "2026-09-29T16:30",
         "attivita": "libro 2"},                                                # ok
        {"fronte": "Esame Lavenia", "inizio": "2026-09-29T16:00", "fine": "2026-09-29T17:00",
         "attivita": "si sovrappone al precedente"},                            # conflitto interno
        {"fronte": "Fronte inventato", "inizio": "2026-09-29T09:00", "fine": "2026-09-29T10:00"},
        {"fronte": "Paper Storia Globale", "inizio": "2026-10-06T09:00", "fine": "2026-10-06T10:30"},
    ],
    "spiegazione": "Settimana con due blocchi.",
    "avvisi": ["Lavenia non ci sta questa settimana: la proiezione passa a rossa"],
}


def occupati():
    occ = logica.espandi_impegni(IMPEGNI, LUNEDI, LUNEDI + timedelta(days=7))
    return logica.occupati_per_piano(occ, ADESSO)


def test_blocchi_sopra_impegni_fissi_vengono_scartati():
    dati = logica.estrai_json("```json\n" + json.dumps(RISPOSTA) + "\n```")
    validi, scartati = logica.valida_blocchi(
        dati["blocchi"], occupati(), {f["nome"] for f in FRONTI},
        datetime(2026, 9, 28), datetime(2026, 10, 5))
    assert [(v["fronte"], v["inizio"]) for v in validi] == [
        ("Paper Storia Globale", "2026-09-28T08:30"), ("Esame Lavenia", "2026-09-29T15:00")]
    motivi = [s["motivo"] for s in scartati]
    assert motivi[0] == "si sovrappone a un impegno: Lezione"
    assert motivi[1] == "si sovrappone a un impegno: Turno bar"
    assert motivi[2] == "si sovrappone a un altro blocco proposto"
    assert motivi[3].startswith("fronte sconosciuto")
    assert motivi[4] == "fuori dal periodo pianificabile"
    # nessun blocco valido tocca un impegno fisso
    for v in validi:
        for o in occupati():
            assert not (logica.a_dt(v["inizio"]) < o["fine_dt"] and logica.a_dt(v["fine"]) > o["inizio_dt"])


def test_input_per_assistente():
    dati = logica.costruisci_input(ADESSO, LUNEDI, "settimana intera", FRONTI, [], IMPEGNI, "Regole")
    assert dati["pianificabile_dal"] == "2026-09-28T00:00"
    assert {i["titolo"] for i in dati["impegni_fissi_e_esistenti"]} == {"Turno bar", "Lezione"}
    assert dati["fasce_libere"]["2026-09-28"] == [["2026-09-28T08:00", "2026-09-28T10:00"],
                                                  ["2026-09-28T12:00", "2026-09-28T22:00"]]
    assert dati["fronti"][0]["ritmo_reale_7_giorni"] == 0
    json.dumps(dati)  # serializzabile


class ClientFinto:
    def __init__(self, testi):
        self.testi = list(testi)
        self.chiamate = 0
        self.messages = self

    def create(self, **kwargs):
        self.chiamate += 1
        return SimpleNamespace(stop_reason="end_turn",
                               content=[SimpleNamespace(type="text", text=self.testi.pop(0))])


def test_json_non_valido_un_solo_nuovo_tentativo():
    client = ClientFinto(["non è json", json.dumps(RISPOSTA)])
    assert assistente.chiedi_piano({}, client=client)["spiegazione"] == "Settimana con due blocchi."
    assert client.chiamate == 2

    client = ClientFinto(["no", "ancora no", json.dumps(RISPOSTA)])
    with pytest.raises(assistente.ErroreAssistente):
        assistente.chiedi_piano({}, client=client)
    assert client.chiamate == 2


def test_senza_chiave_messaggio_chiaro(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert not assistente.chiave_presente()
    with pytest.raises(assistente.ErroreAssistente, match="ANTHROPIC_API_KEY"):
        assistente.chiedi_piano({})


def test_accettazione_sostituisce_solo_blocchi_futuri(conn):
    f = db.crea_fronte(conn, "Paper Storia Globale", "2026-10-15", "parole", 7500)
    passato = db.salva_impegno(conn, "vecchio", "blocco di lavoro", "2026-09-28T09:00:00",
                               "2026-09-28T10:30:00", fronte_id=f, origine="assistente")
    db.salva_impegno(conn, "futuro", "blocco di lavoro", "2026-09-30T09:00:00",
                     "2026-09-30T10:30:00", fronte_id=f, origine="assistente")
    manuale = db.salva_impegno(conn, "mio", "blocco di lavoro", "2026-10-01T09:00:00",
                               "2026-10-01T10:30:00", fronte_id=f)
    pid = db.crea_piano(conn, "2026-09-28", "ripianifica da oggi", {}, {"validi": []}, "")
    nuovo = {"fronte": "Paper Storia Globale", "inizio": "2026-09-30T15:00", "fine": "2026-09-30T16:30",
             "attivita": "cap. 1"}
    db.accetta_blocchi(conn, pid, [nuovo], {"Paper Storia Globale": {"id": f}},
                       datetime(2026, 9, 29, 12), datetime(2026, 10, 5))
    titoli = {i["titolo"]: i for i in db.impegni(conn)}
    assert set(titoli) == {"vecchio", "mio", "cap. 1"}
    assert titoli["cap. 1"]["origine"] == "assistente" and titoli["cap. 1"]["fisso"] == 0
    assert db.piano(conn, pid)["stato"] == "accettato"
    assert passato and manuale


def test_piano_rifiutato_resta_registrato(conn):
    pid = db.crea_piano(conn, "2026-09-28", "settimana intera", {"x": 1}, {"validi": []}, "spieg")
    db.rifiuta_piano(conn, pid)
    assert db.piano(conn, pid)["stato"] == "rifiutato"
    assert db.impegni(conn) == []
