"""Chiamate a Claude e relativi prompt. Tutto il resto dell'app funziona anche senza chiave."""
import base64
import io
import json
import os

from PIL import Image, ImageOps

import config


class ErroreAI(Exception):
    """Errore da mostrare così com'è all'utente."""


def chiave_presente() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def _client(client=None):
    if client is not None:
        return client
    if not chiave_presente():
        raise ErroreAI("Manca la variabile d'ambiente ANTHROPIC_API_KEY: compila i campi a mano.")
    import anthropic
    return anthropic.Anthropic()


# --- immagini ---------------------------------------------------------------

def prepara_foto(dati: bytes) -> bytes:
    """Raddrizza (EXIF), converte in RGB e riduce il lato lungo a LATO_MAX. Restituisce JPEG."""
    try:
        img = Image.open(io.BytesIO(dati))
        img = ImageOps.exif_transpose(img)
    except Exception as e:  # file non immagine o formato non supportato
        raise ErroreAI(f"Impossibile leggere l'immagine: {e}") from e
    img = img.convert("RGB")
    img.thumbnail((config.LATO_MAX, config.LATO_MAX))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85)
    return out.getvalue()


def _blocco_immagine(jpeg: bytes) -> dict:
    return {"type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg",
                       "data": base64.standard_b64encode(jpeg).decode("ascii")}}


# --- chiamata generica ------------------------------------------------------

def _chiedi_json(client, sistema: str, contenuto, schema: dict, max_tokens: int = 8000,
                 messaggi_prec: list | None = None) -> dict:
    """Una chiamata con output JSON vincolato dallo schema."""
    import anthropic
    messaggi = list(messaggi_prec or []) + [{"role": "user", "content": contenuto}]
    try:
        risposta = client.messages.create(
            model=config.MODELLO,
            max_tokens=max_tokens,
            system=sistema,
            messages=messaggi,
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
    except anthropic.AuthenticationError as e:
        raise ErroreAI("Chiave API non valida.") from e
    except anthropic.RateLimitError as e:
        raise ErroreAI("Troppe richieste: riprova tra poco.") from e
    except anthropic.APIStatusError as e:
        raise ErroreAI(f"Errore dell'API ({e.status_code}): {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise ErroreAI("Connessione all'API non riuscita.") from e

    if risposta.stop_reason == "refusal":
        raise ErroreAI("Il modello ha rifiutato la richiesta.")
    if risposta.stop_reason == "max_tokens":
        raise ErroreAI("Risposta troncata: riprova.")
    testo = "".join(b.text for b in risposta.content if b.type == "text")
    try:
        return json.loads(testo)
    except json.JSONDecodeError as e:
        raise ErroreAI("La risposta non era JSON valido.") from e


# --- 1. analisi di un capo ---------------------------------------------------

SISTEMA_CAPO = """Sei un'esperta di moda che cataloga i capi di un armadio personale.
Guardi la foto di UN capo d'abbigliamento o accessorio e ne descrivi le caratteristiche in italiano.
Se nella foto ci sono più capi, descrivi quello più in evidenza.
Colori: nomi semplici in italiano (es. "blu navy", "beige", "bianco"), dal più al meno presente, massimo 4.
Materiale: il più probabile, anche se non ne sei certa (es. "cotone", "lana", "denim", "pelle").
Formalità da 1 (molto informale, es. tuta) a 5 (cerimonia).
Note: una frase breve e utile per abbinarlo (fantasia, vestibilità, dettagli), oppure stringa vuota."""

SCHEMA_CAPO = {
    "type": "object",
    "properties": {
        "categoria": {"type": "string", "enum": config.CATEGORIE},
        "colori": {"type": "array", "items": {"type": "string"}},
        "materiale": {"type": "string"},
        "formalita": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
        "stagione": {"type": "array", "items": {"type": "string", "enum": config.STAGIONI}},
        "stile": {"type": "string", "enum": config.STILI},
        "note": {"type": "string"},
    },
    "required": ["categoria", "colori", "materiale", "formalita", "stagione", "stile", "note"],
    "additionalProperties": False,
}


def analizza_capo(jpeg: bytes, client=None) -> dict:
    """Restituisce i campi del capo precompilati a partire dalla foto (già ridimensionata)."""
    contenuto = [_blocco_immagine(jpeg), {"type": "text", "text": "Cataloga questo capo."}]
    return _chiedi_json(_client(client), SISTEMA_CAPO, contenuto, SCHEMA_CAPO, max_tokens=4000)


# --- 2. assistente outfit ----------------------------------------------------

SISTEMA_OUTFIT = """Sei una consulente d'immagine che aiuta una persona a vestirsi con i capi che possiede già.
Ricevi l'elenco dei suoi capi (solo dati testuali, ognuno con un id), il suo profilo di armocromia,
le sue preferenze di stile, gli ultimi outfit con il giudizio che ha dato, e la situazione per cui si veste.

Regole:
- Usa SOLO capi presenti nell'elenco, citandoli con il loro id esatto. Non inventare capi né id.
- Componi un outfit completo e sensato: di norma un vestito, oppure un top con pantaloni o gonna;
  aggiungi scarpe, capospalla e accessori se ci sono e servono (meteo, occasione).
- Considera occasione, clima indicato, formalità, abbinamento di colori, palette di armocromia e preferenze.
- Impara dai giudizi: ripeti ciò che è piaciuto, evita ciò che non è piaciuto, varia rispetto a ciò che è
  stato indossato di recente.
- Se viene indicato un capo da cui partire, deve far parte dell'outfit.
- "spiegazione": 2-3 frasi in italiano.
- "alternativa_stile": se è utile, suggerisci uno stile diverso da quello più ovvio per l'occasione
  (es. "smart casual" invece di "casual") e spiega perché funzionerebbe meglio; altrimenti null.
- "manca": se un capo che non c'è nell'armadio migliorerebbe molto l'outfit, descrivilo in poche parole
  in modo puramente informativo, senza consigliare di comprarlo, senza marche né negozi; altrimenti null.
- Scrivi tutto in italiano."""

SCHEMA_OUTFIT = {
    "type": "object",
    "properties": {
        "outfit": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"capo_id": {"type": "integer"}, "perche": {"type": "string"}},
                "required": ["capo_id", "perche"],
                "additionalProperties": False,
            },
        },
        "spiegazione": {"type": "string"},
        "alternativa_stile": {
            "anyOf": [
                {"type": "null"},
                {
                    "type": "object",
                    "properties": {"stile": {"type": "string"}, "rispetto_a": {"type": "string"},
                                   "perche": {"type": "string"}},
                    "required": ["stile", "rispetto_a", "perche"],
                    "additionalProperties": False,
                },
            ]
        },
        "manca": {"anyOf": [{"type": "string"}, {"type": "null"}]},
    },
    "required": ["outfit", "spiegazione", "alternativa_stile", "manca"],
    "additionalProperties": False,
}

_CAMPI_CAPO = ("id", "categoria", "colori", "materiale", "formalita", "stagione", "stile", "note")


def dati_outfit(capi: list[dict], profilo: dict, recenti: list[dict]) -> dict:
    """I soli dati testuali da inviare: niente foto."""
    return {
        "capi": [{k: c[k] for k in _CAMPI_CAPO} for c in capi],
        "profilo": {
            "stagione_armocromia": profilo.get("stagione_armocromia") or None,
            "sottotono": profilo.get("sottotono") or None,
            "palette_consigliata": [p["nome"] if isinstance(p, dict) else p
                                    for p in profilo.get("palette_consigliata", [])],
            "colori_da_evitare": profilo.get("colori_da_evitare", []),
            "preferenze_stile": profilo.get("preferenze_stile") or None,
        },
        "ultimi_outfit": [
            {"richiesta": o["richiesta"], "capi_ids": o["capi_ids"],
             "stile_suggerito": o.get("stile_suggerito") or None, "giudizio": o.get("giudizio")}
            for o in recenti
        ],
    }


def valida_outfit(proposta: dict, ids_validi: set[int]) -> tuple[list[dict], list]:
    """Tiene solo i capi esistenti (senza doppioni). Restituisce (voci valide, id scartati)."""
    valide, scartati, visti = [], [], set()
    for voce in proposta.get("outfit", []):
        cid = voce.get("capo_id")
        if isinstance(cid, int) and cid in ids_validi:
            if cid not in visti:
                visti.add(cid)
                valide.append(voce)
        else:
            scartati.append(cid)
    return valide, scartati


def proponi_outfit(richiesta: str, capi: list[dict], profilo: dict, recenti: list[dict],
                   capo_partenza: int | None = None, oggi: str = "", client=None) -> dict:
    """Chiede un outfit. Scarta gli id inesistenti e, se ce n'erano, rigenera una volta."""
    client = _client(client)
    if not capi:
        raise ErroreAI("L'armadio è vuoto: aggiungi qualche capo prima di chiedere un outfit.")
    ids_validi = {c["id"] for c in capi}
    dati = json.dumps(dati_outfit(capi, profilo, recenti), ensure_ascii=False)
    testo = f"Dati:\n{dati}\n\n"
    if oggi:
        testo += f"Data di oggi: {oggi}\n"
    testo += f"Per cosa mi vesto: {richiesta.strip()}\n"
    if capo_partenza is not None:
        testo += f"Capo da cui partire: id {capo_partenza}\n"

    proposta = _chiedi_json(client, SISTEMA_OUTFIT, testo, SCHEMA_OUTFIT)
    valide, scartati = valida_outfit(proposta, ids_validi)
    rigenerato = False
    if scartati or not valide:
        rigenerato = True
        correzione = (f"Questi id non esistono nel mio armadio: {scartati}. " if scartati else
                      "L'outfit era vuoto. ")
        correzione += f"Gli unici id validi sono: {sorted(ids_validi)}. Riproponi l'outfit usando solo quelli."
        precedenti = [{"role": "user", "content": testo},
                      {"role": "assistant", "content": json.dumps(proposta, ensure_ascii=False)}]
        proposta = _chiedi_json(client, SISTEMA_OUTFIT, correzione, SCHEMA_OUTFIT, messaggi_prec=precedenti)
        valide, scartati = valida_outfit(proposta, ids_validi)
    if not valide:
        raise ErroreAI("L'assistente non è riuscito a proporre un outfit con i capi esistenti.")
    proposta["outfit"] = valide
    proposta["scartati"] = scartati
    proposta["rigenerato"] = rigenerato
    return proposta


# --- 3. armocromia -----------------------------------------------------------

SISTEMA_ARMOCROMIA = """Sei una consulente di armocromia. Ricevi da 1 a 3 selfie della stessa persona e stimi,
in modo indicativo, sottotono, stagione cromatica (sistema a 12 stagioni) e palette.
Sii onesta sui limiti: da una foto luce, bilanciamento del bianco, fotocamera, trucco e capelli tinti
alterano i colori, quindi l'affidabilità è al massimo "media" (usa "bassa" se le foto sono poco adatte).
Indica sempre anche la seconda stagione più probabile.
Palette: 10-12 colori che valorizzano la persona; colori da evitare: 4-6. Per ogni colore un nome
in italiano e il codice esadecimale (#RRGGBB).
"limiti": 1-2 frasi su cosa rende incerta la stima in queste foto e come migliorarle.
Scrivi tutto in italiano."""

_COLORE = {
    "type": "object",
    "properties": {"nome": {"type": "string"}, "hex": {"type": "string"}},
    "required": ["nome", "hex"],
    "additionalProperties": False,
}

SCHEMA_ARMOCROMIA = {
    "type": "object",
    "properties": {
        "sottotono": {"type": "string", "enum": config.SOTTOTONI},
        "stagione_armocromia": {"type": "string", "enum": config.STAGIONI_ARMOCROMIA},
        "seconda_stagione": {"type": "string", "enum": config.STAGIONI_ARMOCROMIA},
        "palette_consigliata": {"type": "array", "items": _COLORE},
        "colori_da_evitare": {"type": "array", "items": _COLORE},
        "affidabilita": {"type": "string", "enum": ["bassa", "media"]},
        "limiti": {"type": "string"},
    },
    "required": ["sottotono", "stagione_armocromia", "seconda_stagione", "palette_consigliata",
                 "colori_da_evitare", "affidabilita", "limiti"],
    "additionalProperties": False,
}


def stima_armocromia(jpeg_list: list[bytes], client=None) -> dict:
    """Stima indicativa da 1-3 selfie già ridimensionati."""
    if not 1 <= len(jpeg_list) <= 3:
        raise ErroreAI("Carica da 1 a 3 selfie.")
    contenuto = [_blocco_immagine(j) for j in jpeg_list]
    contenuto.append({"type": "text", "text": "Stima la mia armocromia da queste foto."})
    r = _chiedi_json(_client(client), SISTEMA_ARMOCROMIA, contenuto, SCHEMA_ARMOCROMIA)
    if r.get("affidabilita") not in ("bassa", "media"):  # mai più di "media" da foto
        r["affidabilita"] = "media"
    return r
