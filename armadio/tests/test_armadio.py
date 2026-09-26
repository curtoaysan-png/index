import io
import json
from types import SimpleNamespace

import pytest
from PIL import Image

import ai
import config
import db


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


def test_capi_crud(conn):
    cid = db.aggiungi_capo(conn, _capo(foto=b"\xff\xd8jpeg", colori=["blu", "bianco"]))
    assert db.capo(conn, cid)["colori"] == ["blu", "bianco"]
    assert "foto" not in db.capi(conn)[0]  # l'elenco non carica le foto
    assert db.foto_capo(conn, cid) == b"\xff\xd8jpeg"
    assert db.ids_capi(conn) == {cid}
    db.elimina_capo(conn, cid)
    assert db.capi(conn) == [] and db.foto_capo(conn, cid) is None


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


def test_backup_e_ripristino(conn, tmp_path):
    cid = db.aggiungi_capo(conn, _capo(foto=b"FOTO"))
    db.aggiorna_profilo(conn, preferenze_stile="comoda")
    oid = db.salva_outfit(conn, "cena", [cid], "ok", "", {"manca": None})
    copia = db.backup_in_byte(conn)
    assert copia.startswith(b"SQLite format 3")

    db.elimina_capo(conn, cid)
    db.aggiorna_profilo(conn, preferenze_stile="")
    db.ripristina_backup(conn, copia)
    assert db.foto_capo(conn, cid) == b"FOTO"
    assert db.profilo(conn)["preferenze_stile"] == "comoda"
    assert db.outfit(conn, oid)["capi_ids"] == [cid]
    # Dopo il ripristino i nuovi id non si scontrano con quelli ripristinati.
    assert db.aggiungi_capo(conn, _capo()) > cid


def test_ripristino_rifiuta_file_estranei(conn, tmp_path):
    with pytest.raises(ValueError):
        db.ripristina_backup(conn, b"non un database")
    import sqlite3
    altro = tmp_path / "altro.db"
    sqlite3.connect(altro).execute("CREATE TABLE fronti (id INTEGER)").connection.commit()
    with pytest.raises(ValueError):
        db.ripristina_backup(conn, altro.read_bytes())


def test_sposta_vecchi_dati(tmp_path):
    """Il database della prima versione (armadio/data, foto come file) viene spostato."""
    import sqlite3
    vecchia = tmp_path / "app" / "data"
    (vecchia / "foto").mkdir(parents=True)
    (vecchia / "foto" / "a.jpg").write_bytes(b"JPG")
    v = sqlite3.connect(vecchia / "armadio.db")
    v.execute("CREATE TABLE capi (id INTEGER PRIMARY KEY AUTOINCREMENT, foto_path TEXT, categoria TEXT NOT NULL,"
              " colori TEXT NOT NULL DEFAULT '[]', materiale TEXT DEFAULT '', formalita INTEGER DEFAULT 3,"
              " stagione TEXT NOT NULL DEFAULT '[]', stile TEXT DEFAULT '', note TEXT DEFAULT '',"
              " aggiunto_il TEXT NOT NULL)")
    v.execute("INSERT INTO capi (foto_path, categoria, aggiunto_il) VALUES ('data/foto/a.jpg', 'top', 'x')")
    v.commit()
    v.close()

    nuovo = tmp_path / "AppData" / "armadio.db"
    assert db.sposta_vecchi_dati(nuovo, vecchia)
    c = db.connetti(nuovo)
    assert db.foto_capo(c, 1) == b"JPG"
    assert (vecchia / "armadio.db.spostato").exists() and not (vecchia / "armadio.db").exists()
    assert not db.sposta_vecchi_dati(nuovo, vecchia)  # seconda volta: niente da fare


def test_schema_postgres():
    s = db.schema_pg()
    assert "SERIAL PRIMARY KEY" in s and "BYTEA" in s and "AUTOINCREMENT" not in s


def test_postgres_letture_non_lasciano_transazioni_aperte(conn):
    if not isinstance(conn, db.ConnessionePg):
        pytest.skip("solo Postgres")
    db.aggiungi_capo(conn, _capo())
    db.capi(conn)
    db.profilo(conn)
    assert not conn.in_transazione
