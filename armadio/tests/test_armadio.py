import io
import json
from types import SimpleNamespace

import pytest
from PIL import Image

import ai
import config
import db


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "BASE", tmp_path)
    return db.connetti(tmp_path / "t.db")


def _capo(**kw):
    base = {"categoria": "top", "colori": ["blu"], "materiale": "cotone", "formalita": 2,
            "stagione": ["estate"], "stile": "casual", "note": ""}
    return {**base, **kw}


class ClientFinto:
    """Restituisce in sequenza le risposte JSON indicate e registra le chiamate."""

    def __init__(self, *risposte):
        self.risposte = list(risposte)
        self.chiamate = []
        self.messages = self

    def create(self, **kw):
        self.chiamate.append(kw)
        testo = json.dumps(self.risposte.pop(0))
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=testo)])


def test_capi_crud(conn, tmp_path):
    foto = tmp_path / "data" / "foto" / "x.jpg"
    foto.parent.mkdir(parents=True)
    foto.write_bytes(b"x")
    cid = db.aggiungi_capo(conn, _capo(foto_path="data/foto/x.jpg", colori=["blu", "bianco"]))
    assert db.capo(conn, cid)["colori"] == ["blu", "bianco"]
    assert db.ids_capi(conn) == {cid}
    db.elimina_capo(conn, cid)
    assert db.capi(conn) == [] and not foto.exists()


def test_profilo_e_giudizio(conn):
    db.aggiorna_profilo(conn, stagione_armocromia="autunno soft",
                        palette_consigliata=[{"nome": "salvia", "hex": "#9CAF88"}])
    assert db.profilo(conn)["palette_consigliata"][0]["nome"] == "salvia"
    oid = db.salva_outfit(conn, "cena", [1], "ok", "", {})
    db.imposta_giudizio(conn, oid, "mi piace")
    assert db.outfit_recenti(conn)[0]["giudizio"] == "mi piace"
    with pytest.raises(ValueError):
        db.imposta_giudizio(conn, oid, "boh")


def test_prepara_foto_ridimensiona():
    buf = io.BytesIO()
    Image.new("RGBA", (3000, 1500), (255, 0, 0, 255)).save(buf, format="PNG")
    out = Image.open(io.BytesIO(ai.prepara_foto(buf.getvalue())))
    assert out.format == "JPEG" and max(out.size) == config.LATO_MAX


def test_senza_chiave(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert not ai.chiave_presente()
    with pytest.raises(ai.ErroreAI):
        ai.analizza_capo(b"")


def test_valida_outfit():
    valide, scartati = ai.valida_outfit(
        {"outfit": [{"capo_id": 1, "perche": ""}, {"capo_id": 99, "perche": ""},
                    {"capo_id": 1, "perche": ""}, {"capo_id": "2", "perche": ""}]}, {1, 2})
    assert [v["capo_id"] for v in valide] == [1] and scartati == [99, "2"]


def _proposta(*ids):
    return {"outfit": [{"capo_id": i, "perche": "p"} for i in ids], "spiegazione": "s",
            "alternativa_stile": None, "manca": None}


def test_outfit_rigenera_una_volta_se_id_inesistenti():
    capi = [dict(_capo(), id=1), dict(_capo(categoria="pantaloni"), id=2)]
    client = ClientFinto(_proposta(1, 42), _proposta(1, 2))
    r = ai.proponi_outfit("cena", capi, {}, [], client=client)
    assert [v["capo_id"] for v in r["outfit"]] == [1, 2] and r["rigenerato"]
    assert len(client.chiamate) == 2
    # Al modello vanno solo dati testuali: nessuna immagine.
    assert "image" not in json.dumps(client.chiamate[0]["messages"])


def test_outfit_scarta_id_inesistenti_anche_dopo_rigenerazione():
    capi = [dict(_capo(), id=1)]
    r = ai.proponi_outfit("cena", capi, {}, [], client=ClientFinto(_proposta(1, 42), _proposta(1, 43)))
    assert [v["capo_id"] for v in r["outfit"]] == [1] and r["scartati"] == [43]


def test_outfit_nessun_capo_valido():
    capi = [dict(_capo(), id=1)]
    with pytest.raises(ai.ErroreAI):
        ai.proponi_outfit("cena", capi, {}, [], client=ClientFinto(_proposta(7), _proposta(8)))


def test_armocromia_affidabilita_massima_media():
    r = ai.stima_armocromia([b"x"], client=ClientFinto({"affidabilita": "alta"}))
    assert r["affidabilita"] == "media"


def test_colori_testo_andata_ritorno():
    colori = [{"nome": "blu navy", "hex": "#1F2A44"}, {"nome": "salvia", "hex": ""}]
    assert db.testo_a_colori(db.colori_a_testo(colori)) == colori
